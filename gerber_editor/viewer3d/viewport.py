"""Hardware-rendered board preview with orbit, pan, zoom and standard views."""

import math

import numpy as np
from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QMatrix4x4, QSurfaceFormat, QVector3D
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLFunctions_3_3_Core,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

VERTEX_SHADER = """#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
uniform mat4 mvp;
uniform mat4 model;
out vec3 n;
out vec3 worldPosition;
void main() { gl_Position = mvp * vec4(position, 1.0); n = mat3(model) * normal; worldPosition = vec3(model * vec4(position, 1.0)); }
"""
FRAGMENT_SHADER = """#version 330 core
in vec3 n;
in vec3 worldPosition;
uniform vec3 color;
uniform vec3 eye;
uniform int realistic;
uniform int material;
out vec4 frag;
void main() {
  vec3 N = normalize(n);
  if (realistic == 0) {
    float light = 0.34 + 0.66 * abs(dot(N, normalize(vec3(-0.3, -0.5, 1.0))));
    frag = vec4(color * light, 1.0); return;
  }
  vec3 V = normalize(eye - worldPosition);
  if (dot(N, V) < 0.0) N = -N;
  vec3 L = normalize(vec3(-0.4, -0.6, 1.0));
  vec3 fill = normalize(V + vec3(0.4, 0.3, 0.3));
  float diffuse = 0.25 + 0.5 * max(dot(N, L), 0.0) + 0.25 * max(dot(N, fill), 0.0);
  float power = material == 1 ? 90.0 : (material == 2 ? 115.0 : 22.0);
  float strength = material == 1 ? 0.75 : (material == 2 ? 0.30 : 0.06);
  float specular = pow(max(dot(N, normalize(L + V)), 0.0), power) * strength;
  float grain = material == 2 ? 0.985 + 0.015 * sin(worldPosition.x * 120.0) * sin(worldPosition.y * 120.0) : 1.0;
  vec3 result = color * diffuse * grain + vec3(specular);
  frag = vec4(pow(clamp(result, 0.0, 1.0), vec3(0.68)), 1.0);
}
"""


class BoardViewport(QOpenGLWidget):
    failure = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        self.setFormat(fmt)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mesh = None
        self.hidden = set()
        self.yaw, self.pitch = -55.0, 50.0
        self.distance = 100.0
        self.pan_x = self.pan_y = self.pan_z = 0.0
        self.flip_angle = 0.0
        self.realistic = True
        self.flip_animation = QVariantAnimation(self)
        self.flip_animation.setDuration(550)
        self.flip_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.flip_animation.valueChanged.connect(self._flip_frame)
        self.perspective = True
        self._press = None
        self._upload = False
        self.error = ""
        self.functions = None

    def set_mesh(self, mesh):
        first = self.mesh is None
        self.mesh = mesh
        self._upload = True
        if first and mesh is not None:
            self.fit_all()
        self.update()

    def fit_all(self):
        if self.mesh:
            self.distance = max(self.mesh.size[:2]) * 1.65 + 1
        self.pan_x = self.pan_y = self.pan_z = 0
        self.update()

    def _flip_frame(self, value):
        self.flip_angle = float(value)
        self.update()

    def flip_board(self, animated=True):
        destination = 180.0 if math.cos(math.radians(self.flip_angle)) >= 0 else 360.0
        self.flip_animation.stop()
        if animated:
            self.flip_animation.setStartValue(self.flip_angle % 360)
            self.flip_animation.setEndValue(destination)
            self.flip_animation.start()
        else:
            self._flip_frame(destination % 360)

    def standard_view(self, name):
        self.yaw, self.pitch = {
            "top": (-90, 89.99),
            "bottom": (90, -89.99),
            "iso": (-55, 50),
            "front": (-90, 0),
            "right": (0, 0),
        }[name]
        self.update()

    def initializeGL(self):
        try:
            self.functions = QOpenGLFunctions_3_3_Core()
            if not self.functions.initializeOpenGLFunctions():
                raise RuntimeError("OpenGL 3.3 não está disponível neste computador.")
            self.program = QOpenGLShaderProgram(self)
            for kind, source in (
                (QOpenGLShader.ShaderTypeBit.Vertex, VERTEX_SHADER),
                (QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT_SHADER),
            ):
                if not self.program.addShaderFromSourceCode(kind, source):
                    raise RuntimeError(self.program.log())
            if not self.program.link():
                raise RuntimeError(self.program.log())
            self.buffer = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self.buffer.create()
            self.vao = QOpenGLVertexArrayObject(self)
            self.vao.create()
            self.functions.glEnable(0x0B71)  # GL_DEPTH_TEST
            self.functions.glClearColor(0.065, 0.078, 0.10, 1.0)
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = str(exc)
            self.failure.emit(self.error)

    def cleanup(self):
        self.makeCurrent()
        if hasattr(self, "buffer"):
            self.buffer.destroy()
            self.vao.destroy()
        self.doneCurrent()

    def paintGL(self):
        ratio = self.devicePixelRatioF()
        self._render(round(self.width() * ratio), round(self.height() * ratio))

    def _render(self, width, height):
        if not self.functions or self.error:
            return
        gl = self.functions
        gl.glViewport(0, 0, width, height)
        gl.glClear(0x00004000 | 0x00000100)
        if not self.mesh:
            return
        self.vao.bind()
        self.buffer.bind()
        if self._upload:
            data = (
                np.concatenate([part.vertices for part in self.mesh.parts])
                .astype(np.float32, copy=False)
                .tobytes()
            )
            self.buffer.allocate(data, len(data))
            self._upload = False
        self.program.bind()
        self.program.enableAttributeArray(0)
        self.program.enableAttributeArray(1)
        self.program.setAttributeBuffer(0, 0x1406, 0, 3, 24)
        self.program.setAttributeBuffer(1, 0x1406, 12, 3, 24)
        aspect = width / max(height, 1)
        projection = QMatrix4x4()
        if self.perspective:
            projection.perspective(
                40,
                aspect,
                max(0.001, self.distance * 0.03),
                self.distance + max(self.mesh.size) * 3 + 1,
            )
        else:
            scale = self.distance * 0.35
            projection.ortho(
                -scale * aspect,
                scale * aspect,
                -scale,
                scale,
                -self.distance * 20,
                self.distance * 20,
            )
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        eye = QVector3D(
            self.distance * math.cos(pitch) * math.cos(yaw),
            self.distance * math.cos(pitch) * math.sin(yaw),
            self.distance * math.sin(pitch),
        )
        target = QVector3D(self.pan_x, self.pan_y, self.pan_z)
        view = QMatrix4x4()
        view.lookAt(eye + target, target, QVector3D(0, 0, 1))
        model = QMatrix4x4()
        model.rotate(self.flip_angle, 0, 1, 0)
        self.program.setUniformValue("mvp", projection * view * model)
        self.program.setUniformValue("model", model)
        self.program.setUniformValue("eye", eye + target)
        self.program.setUniformValue("realistic", int(self.realistic))
        start = 0
        for part in self.mesh.parts:
            if part.key not in self.hidden:
                self.program.setUniformValue("color", QVector3D(*part.color))
                self.program.setUniformValue(
                    "material",
                    {"fr4": 0, "copper": 1, "mask": 2, "silk": 3, "paste": 4}.get(part.material, 0),
                )
                gl.glDrawArrays(0x0004, start, len(part.vertices))
            start += len(part.vertices)
        self.program.release()
        self.buffer.release()
        self.vao.release()

    def capture_image(self, width, height):
        if not self.mesh or not self.isValid() or self.error:
            raise ValueError("O modelo 3D ainda não está pronto.")
        if not (64 <= width <= 8192 and 64 <= height <= 8192) or width * height > 32000000:
            raise ValueError("A resolução deve estar entre 64 e 8192 pixels, até 32 megapixels.")
        self.makeCurrent()
        framebuffer = None
        try:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
            framebuffer = QOpenGLFramebufferObject(width, height, fmt)
            if not framebuffer.isValid() or not framebuffer.bind():
                raise ValueError("A GPU não suporta esta resolução.")
            self._render(width, height)
            image = framebuffer.toImage()
            if image.isNull():
                raise ValueError("Não foi possível renderizar a imagem.")
            return image
        finally:
            self.functions.glBindFramebuffer(0x8D40, self.defaultFramebufferObject())
            framebuffer = None
            self.doneCurrent()
            self.update()

    def pan_by(self, dx, dy):
        scale = self.distance / max(1, self.height()) * 0.65
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        self.pan_x += (dx * math.sin(yaw) - dy * math.sin(pitch) * math.cos(yaw)) * scale
        self.pan_y += (-dx * math.cos(yaw) - dy * math.sin(pitch) * math.sin(yaw)) * scale
        self.pan_z += dy * math.cos(pitch) * scale
        self.update()

    def mousePressEvent(self, event):
        self._press = event.position()

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        delta = event.position() - self._press
        self._press = event.position()
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.yaw -= delta.x() * 0.5
            self.pitch = max(-89.99, min(89.99, self.pitch + delta.y() * 0.5))
        else:
            self.pan_by(delta.x(), delta.y())
        self.update()

    def mouseReleaseEvent(self, event):
        self._press = None

    def wheelEvent(self, event):
        self.distance = min(
            100000, max(0.1, self.distance * 0.85 ** (event.angleDelta().y() / 120))
        )
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Home:
            self.fit_all()
        elif event.key() == Qt.Key.Key_Escape:
            self.window().close()
        elif event.key() == Qt.Key.Key_F:
            self.flip_board()
        else:
            super().keyPressEvent(event)
