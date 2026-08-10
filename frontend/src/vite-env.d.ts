/// <reference types="vite/client" />

declare module 'three' {
  export class Scene {
    constructor();
    add(object: any): void;
    remove(object: any): void;
  }
  export class PerspectiveCamera {
    constructor(fov: number, aspect: number, near: number, far: number);
    position: { x: number; y: number; z: number };
  }
  export class WebGLRenderer {
    constructor(params: any);
    setSize(width: number, height: number): void;
    setPixelRatio(ratio: number): void;
    render(scene: Scene, camera: PerspectiveCamera): void;
    dispose(): void;
    domElement: HTMLElement;
  }
  export class IcosahedronGeometry {
    constructor(radius: number, detail: number, ...args: any[]);
  }
  export class MeshBasicMaterial {
    constructor(params: any);
  }
  export class Mesh {
    constructor(geometry: any, material: any);
    position: { x: number; y: number; z: number };
    rotation: { x: number; y: number; z: number };
  }
  export class Group {
    add(object: any): void;
    rotation: { x: number; y: number; z: number };
  }
  export class Clock {
    getElapsedTime(): number;
  }
}

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_CLERK_PUBLISHABLE_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
