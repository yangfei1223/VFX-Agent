// shader-renderer.ts
import * as THREE from "three";

const VERTEX_SHADER = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

// Shadertoy 兼容的片段着色器包装
function wrapFragmentShader(userShader: string): string {
  return `
precision highp float;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec2 u_mouse;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
varying vec2 vUv;

${userShader}

void main() {
  vec4 fragColor;
  mainImage(fragColor, gl_FragCoord.xy);
  gl_FragColor = fragColor;
}
`;
}

export class ShaderRenderer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.OrthographicCamera;
  private mesh: THREE.Mesh | null = null;
  private clock: THREE.Clock;
  private animationId: number | null = null;
  private mousePos = new THREE.Vector2(0, 0);
  private backdropTexture: THREE.Texture | null = null;
  private userTexture: THREE.Texture | null = null;
  private defaultTexture: THREE.Texture;

  constructor(container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.clock = new THREE.Clock();

    // 默认 1x1 白色纹理（未绑定 channel 时使用，避免采样报错）
    const canvas = document.createElement("canvas");
    canvas.width = 1; canvas.height = 1;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, 1, 1);
    this.defaultTexture = new THREE.CanvasTexture(canvas);
  }

  compileShader(fragShaderSource: string): { success: boolean; error: string | null } {
    const fullFrag = wrapFragmentShader(fragShaderSource);

    // 清除旧的 mesh
    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      (this.mesh.material as THREE.ShaderMaterial).dispose();
      this.mesh = null;
    }

    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: fullFrag,
      uniforms: {
        u_time: { value: 0.0 },
        u_resolution: { value: new THREE.Vector2(
          this.renderer.domElement.width,
          this.renderer.domElement.height
        )},
        u_mouse: { value: this.mousePos },
        // 纹理通道：iChannel0 = 系统backdrop, iChannel1 = 用户纹理
        iChannel0: { value: this.backdropTexture || this.defaultTexture },
        iChannel1: { value: this.userTexture || this.defaultTexture },
      },
    });

    // 检查编译错误
    const gl = this.renderer.getContext();
    gl.getParameter(gl.CURRENT_PROGRAM);

    const geometry = new THREE.PlaneGeometry(2, 2);
    this.mesh = new THREE.Mesh(geometry, material);
    this.scene.add(this.mesh);

    // 尝试编译
    this.renderer.render(this.scene, this.camera);

    const program = (material as any).program;
    if (program) {
      const diagnostics = program.getDiagnostics();
      if (diagnostics && diagnostics.fragmentShaderLog) {
        return { success: false, error: diagnostics.fragmentShaderLog };
      }
    }

    return { success: true, error: null };
  }

  startRendering() {
    this.clock.start();
    const animate = () => {
      this.animationId = requestAnimationFrame(animate);
      if (this.mesh) {
        const mat = (this.mesh.material as THREE.ShaderMaterial);
        mat.uniforms.u_time.value = this.clock.getElapsedTime();
        mat.uniforms.u_resolution.value.set(
          this.renderer.domElement.width,
          this.renderer.domElement.height
        );
      }
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  stopRendering() {
    if (this.animationId !== null) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }

  updateMouse(x: number, y: number) {
    const canvas = this.renderer.domElement;
    this.mousePos.set(x, canvas.height - y);
  }

  setTime(t: number) {
    // 设置渲染时间（供 Playwright 截图时控制动画帧）
    if (this.mesh) {
      const mat = (this.mesh.material as THREE.ShaderMaterial);
      mat.uniforms.u_time.value = t;
    }
    this.renderer.render(this.scene, this.camera);
  }

  resize(width: number, height: number) {
    this.renderer.setSize(width, height);
    if (this.mesh) {
      const mat = (this.mesh.material as THREE.ShaderMaterial);
      mat.uniforms.u_resolution.value.set(width * devicePixelRatio, height * devicePixelRatio);
    }
  }

  dispose() {
    this.stopRendering();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}