"use client";

import { useEffect, useRef } from "react";
import styles from "./OraktSignalField.module.css";

export type OraktSignalFieldProps = Readonly<{
  /** Optional positioning hook for the surface that owns the field. */
  className?: string;
  /** Visual energy multiplier. Values between 0.6 and 1.4 work best. */
  intensity?: number;
  /** Caps backing-store resolution while preserving high-DPI rendering. */
  maxDpr?: number;
  /** Animation speed multiplier. */
  speed?: number;
}>;

type SignalParticle = Readonly<{
  x: number;
  y: number;
  drift: number;
  phase: number;
  size: number;
  speed: number;
}>;

type HelixPoint = Readonly<{
  x: number;
  y: number;
  depth: number;
}>;

const TAU = Math.PI * 2;

/** A GPU-rendered silk volume; the 2D field remains the low-power fallback. */
function createSilkRenderer(canvas: HTMLCanvasElement) {
  const gl = canvas.getContext("webgl", { alpha: true, antialias: false, depth: false, powerPreference: "low-power" });
  if (!gl) return null;
  const vertex = gl.createShader(gl.VERTEX_SHADER)!;
  gl.shaderSource(vertex, "attribute vec2 p; void main(){gl_Position=vec4(p,0.,1.);}");
  gl.compileShader(vertex);
  const fragment = gl.createShader(gl.FRAGMENT_SHADER)!;
  gl.shaderSource(fragment, `
    precision mediump float;
    uniform vec2 resolution;
    uniform float time;
    float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
    float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
    float fbm(vec2 p){float v=0.;float a=.5;for(int i=0;i<4;i++){v+=a*noise(p);p=mat2(.8,-.6,.6,.8)*p*2.03+4.7;a*=.5;}return v;}
    void main(){
      vec2 uv=gl_FragCoord.xy/resolution;
      vec2 p=(uv-.5)*vec2(resolution.x/resolution.y,1.);
      float t=time*.065;
      vec2 q=vec2(fbm(p*1.5+vec2(t,-t*.4)),fbm(p*1.6+vec2(4.2,-t*.7)));
      float field=fbm(p*2.0+q*2.5+vec2(t*.4,0.));
      float fold=p.y+.16*sin(p.x*2.7+t)+.36*(field-.5);
      float folds=pow(.5+.5*sin(fold*31.+field*8.),7.);
      float filaments=pow(.5+.5*sin(fold*175.+field*18.),18.);
      float curtain=exp(-pow((fold+.04)*2.1,2.));
      float energy=curtain*(.18+folds*.78+filaments*.1);
      vec3 purple=vec3(.28,.065,.82),blue=vec3(.015,.36,.85),cyan=vec3(.08,.76,.93);
      vec3 color=mix(purple,blue,.5+.5*sin(p.x*2.4+field*3.+t*.8));
      color=mix(color,cyan,folds*.22);
      float right=smoothstep(.08,.72,uv.x);
      float grain=(hash(gl_FragCoord.xy)-.5)*.012;
      color=color*energy*(.35+right*.95)+vec3(.008,.005,.022)+grain;
      gl_FragColor=vec4(color,.95);
    }
  `);
  gl.compileShader(fragment);
  const program = gl.createProgram()!;
  gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); return null;
  }
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,1,1]), gl.STATIC_DRAW);
  gl.useProgram(program);
  const position = gl.getAttribLocation(program,"p");
  gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
  const size = gl.getUniformLocation(program,"resolution"), clock = gl.getUniformLocation(program,"time");
  return {
    draw(time: number) { gl.viewport(0,0,canvas.width,canvas.height); gl.uniform2f(size,canvas.width,canvas.height); gl.uniform1f(clock,time); gl.drawArrays(gl.TRIANGLE_STRIP,0,4); },
    dispose() { gl.deleteBuffer(buffer); gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); },
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function seededParticles(count: number): SignalParticle[] {
  let seed = 0x51a7f13d;

  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };

  return Array.from({ length: count }, () => ({
    x: random(),
    y: random(),
    drift: 0.012 + random() * 0.035,
    phase: random() * TAU,
    size: 0.45 + random() * 1.35,
    speed: 0.004 + random() * 0.012,
  }));
}

const PARTICLES = seededParticles(58);

function traceFluidRibbon(
  width: number,
  height: number,
  time: number,
  band: number,
) {
  const path = new Path2D();
  const samples = 72;

  for (let index = 0; index <= samples; index += 1) {
    const progress = index / samples;
    const x = width * (progress * 1.18 - 0.09);
    const base = height * (0.19 + band * 0.13);
    const primary = Math.sin(progress * TAU * 1.08 + time * 0.11 + band * 1.31);
    const secondary = Math.sin(progress * TAU * 2.4 - time * 0.07 + band * 0.77);
    const y = base + primary * height * 0.068 + secondary * height * 0.018;

    if (index === 0) path.moveTo(x, y);
    else path.lineTo(x, y);
  }

  return path;
}

function getHelixPoint(
  progress: number,
  phaseOffset: number,
  width: number,
  height: number,
  time: number,
  mobile: boolean,
): HelixPoint {
  const edgeFade = Math.pow(Math.sin(progress * Math.PI), 0.42);
  const phase = progress * TAU * 3.15 - time * 0.56 + phaseOffset;
  const radius = Math.min(width, height) * (mobile ? 0.064 : 0.083) * edgeFade;
  const centerX = width * (-0.075 + progress * 1.15);
  const centerY =
    height * (0.58 - progress * 0.19) +
    Math.sin(progress * TAU * 1.12 + time * 0.13) * height * 0.055;

  return {
    x: centerX + Math.cos(phase) * radius * 0.34,
    y: centerY + Math.sin(phase) * radius,
    depth: Math.cos(phase),
  };
}

function strokePath(
  context: CanvasRenderingContext2D,
  path: Path2D,
  color: CanvasGradient | string,
  width: number,
  alpha: number,
  blur = 0,
) {
  context.save();
  context.strokeStyle = color;
  context.lineWidth = width;
  context.globalAlpha = alpha;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.filter = blur > 0 ? `blur(${blur}px)` : "none";
  context.stroke(path);
  context.restore();
}

function drawAtmosphere(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
  intensity: number,
  mobile: boolean,
) {
  const shortestSide = Math.min(width, height);
  const bandCount = mobile ? 3 : 5;
  const wash = context.createRadialGradient(
    width * 0.68,
    height * 0.43,
    0,
    width * 0.68,
    height * 0.43,
    Math.max(width, height) * 0.72,
  );
  wash.addColorStop(0, `rgba(75, 47, 214, ${0.095 * intensity})`);
  wash.addColorStop(0.42, `rgba(18, 100, 224, ${0.055 * intensity})`);
  wash.addColorStop(1, "rgba(3, 2, 11, 0)");
  context.fillStyle = wash;
  context.fillRect(0, 0, width, height);

  context.globalCompositeOperation = "screen";

  for (let band = 0; band < bandCount; band += 1) {
    const path = traceFluidRibbon(width, height, time, band);
    const gradient = context.createLinearGradient(0, height, width, 0);
    const shift = 0.5 + Math.sin(time * 0.17 + band) * 0.08;
    gradient.addColorStop(0, "rgba(37, 20, 122, 0)");
    gradient.addColorStop(0.18, "rgba(92, 48, 236, .34)");
    gradient.addColorStop(shift, "rgba(23, 190, 255, .42)");
    gradient.addColorStop(0.78, "rgba(119, 64, 255, .3)");
    gradient.addColorStop(1, "rgba(19, 219, 255, 0)");
    const ribbonWidth = shortestSide * (0.024 + band * 0.0045);

    strokePath(
      context,
      path,
      gradient,
      ribbonWidth * 3.4,
      (0.09 + band * 0.008) * intensity,
      mobile ? 11 : 18,
    );
    strokePath(context, path, gradient, ribbonWidth, 0.18 * intensity, mobile ? 3 : 6);
    strokePath(context, path, "rgba(179, 224, 255, .48)", 0.65, 0.24 * intensity);
  }

  const filamentCount = mobile ? 5 : 9;
  for (let index = 0; index < filamentCount; index += 1) {
    const path = traceFluidRibbon(width, height, time * (0.82 + index * 0.015), index * 0.47);
    const hue = 194 + (index % 4) * 19;
    strokePath(
      context,
      path,
      `hsla(${hue}, 100%, 72%, .55)`,
      0.48 + (index % 3) * 0.24,
      (0.1 + (index % 2) * 0.05) * intensity,
    );
  }

  context.globalCompositeOperation = "source-over";
}

function drawHelix(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
  intensity: number,
  mobile: boolean,
) {
  const sampleCount = mobile ? 66 : 104;
  const strandA: HelixPoint[] = [];
  const strandB: HelixPoint[] = [];
  const pathA = new Path2D();
  const pathB = new Path2D();

  for (let index = 0; index <= sampleCount; index += 1) {
    const progress = index / sampleCount;
    const pointA = getHelixPoint(progress, 0, width, height, time, mobile);
    const pointB = getHelixPoint(progress, Math.PI, width, height, time, mobile);
    strandA.push(pointA);
    strandB.push(pointB);

    if (index === 0) {
      pathA.moveTo(pointA.x, pointA.y);
      pathB.moveTo(pointB.x, pointB.y);
    } else {
      pathA.lineTo(pointA.x, pointA.y);
      pathB.lineTo(pointB.x, pointB.y);
    }
  }

  context.globalCompositeOperation = "screen";

  const helixGradient = context.createLinearGradient(width * 0.05, height, width * 0.95, 0);
  helixGradient.addColorStop(0, "rgba(105, 45, 255, .18)");
  helixGradient.addColorStop(0.28, "rgba(57, 128, 255, .78)");
  helixGradient.addColorStop(0.54, "rgba(24, 226, 255, .88)");
  helixGradient.addColorStop(0.76, "rgba(141, 69, 255, .82)");
  helixGradient.addColorStop(1, "rgba(42, 215, 255, .12)");
  strokePath(context, pathA, helixGradient, mobile ? 8 : 13, 0.28 * intensity, mobile ? 6 : 11);
  strokePath(context, pathB, helixGradient, mobile ? 8 : 13, 0.24 * intensity, mobile ? 6 : 11);

  context.save();
  context.lineCap = "round";

  for (let index = 3; index < sampleCount - 3; index += mobile ? 7 : 6) {
    const progress = index / sampleCount;
    const a = strandA[index];
    const b = strandB[index];
    const depth = (a.depth + 1) * 0.5;
    const hue = 194 + Math.sin(progress * TAU * 1.5 + time * 0.22) * 35 + depth * 36;
    const rungGradient = context.createLinearGradient(a.x, a.y, b.x, b.y);
    rungGradient.addColorStop(0, `hsla(${hue}, 100%, 70%, ${0.12 + depth * 0.2})`);
    rungGradient.addColorStop(0.5, "rgba(191, 214, 255, .07)");
    rungGradient.addColorStop(1, `hsla(${hue + 48}, 100%, 72%, ${0.23 - depth * 0.09})`);
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.lineWidth = 0.55 + depth * 0.45;
    context.strokeStyle = rungGradient;
    context.globalAlpha = intensity;
    context.stroke();
  }

  for (let index = 1; index <= sampleCount; index += 1) {
    const progress = index / sampleCount;
    const previousA = strandA[index - 1];
    const currentA = strandA[index];
    const previousB = strandB[index - 1];
    const currentB = strandB[index];

    for (const [strandIndex, previous, current] of [
      [0, previousA, currentA],
      [1, previousB, currentB],
    ] as const) {
      const depth = (current.depth + 1) * 0.5;
      const phase = progress * TAU * 1.4 + time * 0.18 + strandIndex * Math.PI;
      const hue = 203 + 54 * (0.5 + Math.sin(phase) * 0.5);
      context.beginPath();
      context.moveTo(previous.x, previous.y);
      context.lineTo(current.x, current.y);
      context.strokeStyle = `hsla(${hue}, 100%, ${68 + depth * 16}%, ${0.28 + depth * 0.66})`;
      context.lineWidth = (0.75 + depth * (mobile ? 1.2 : 1.8)) * intensity;
      context.globalAlpha = 0.78;
      context.stroke();
    }
  }

  context.restore();

  const nodeCount = mobile ? 3 : 6;
  for (let index = 0; index < nodeCount; index += 1) {
    const progress = (time * (0.031 + index * 0.0017) + index / nodeCount) % 1;
    const phaseOffset = index % 2 === 0 ? 0 : Math.PI;
    const point = getHelixPoint(progress, phaseOffset, width, height, time, mobile);
    const radius = (mobile ? 8 : 12) * (0.8 + (point.depth + 1) * 0.18) * intensity;
    const glow = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
    glow.addColorStop(0, "rgba(234, 251, 255, .95)");
    glow.addColorStop(0.18, index % 2 === 0 ? "rgba(35, 222, 255, .86)" : "rgba(153, 86, 255, .86)");
    glow.addColorStop(1, "rgba(80, 48, 255, 0)");
    context.fillStyle = glow;
    context.globalAlpha = 0.62 + point.depth * 0.14;
    context.beginPath();
    context.arc(point.x, point.y, radius, 0, TAU);
    context.fill();
  }

  context.globalAlpha = 1;
  context.globalCompositeOperation = "source-over";
}

function drawParticles(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
  intensity: number,
  mobile: boolean,
) {
  const count = mobile ? 20 : PARTICLES.length;
  context.save();
  context.globalCompositeOperation = "screen";

  for (let index = 0; index < count; index += 1) {
    const particle = PARTICLES[index];
    const progress = (particle.x + time * particle.speed) % 1;
    const x = progress * width;
    const y =
      particle.y * height +
      Math.sin(progress * TAU * 1.7 + particle.phase + time * particle.drift) * height * 0.034;
    const alpha = (0.09 + 0.16 * Math.sin(progress * Math.PI)) * intensity;
    context.strokeStyle = index % 3 === 0 ? "rgba(166, 102, 255, .7)" : "rgba(73, 218, 255, .68)";
    context.globalAlpha = alpha;
    context.lineWidth = particle.size;
    context.beginPath();
    context.moveTo(x - particle.size * 5.5, y + particle.size * 1.5);
    context.lineTo(x, y);
    context.stroke();
  }

  context.restore();
}

export function OraktSignalField({
  className,
  intensity = 1,
  maxDpr = 2,
  speed = 1,
}: OraktSignalFieldProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const silkRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    const canvas = canvasRef.current;
    if (!root || !canvas) return;

    const context = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!context) return;
    const silkCanvas = silkRef.current;
    const silk = silkCanvas ? createSilkRenderer(silkCanvas) : null;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const mobileQuery = window.matchMedia("(max-width: 720px), (pointer: coarse)");
    const safeIntensity = clamp(intensity, 0, 2);
    const safeSpeed = clamp(speed, 0.15, 2.5);
    const dprLimit = clamp(maxDpr, 1, 3);
    let width = 1;
    let height = 1;
    let isIntersecting = true;
    let frame: number | null = null;
    let lastPaint = 0;

    const draw = (timestamp: number) => {
      const mobile = mobileQuery.matches;
      const time = (timestamp / 1000) * safeSpeed;
      silk?.draw(time);
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.setTransform(canvas.width / width, 0, 0, canvas.height / height, 0, 0);
      drawAtmosphere(context, width, height, time, safeIntensity, mobile);
      drawParticles(context, width, height, time, safeIntensity, mobile);
      drawHelix(context, width, height, time, safeIntensity, mobile);
    };

    const stop = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
    };

    const animate = (timestamp: number) => {
      frame = null;
      if (document.hidden || !isIntersecting || motionQuery.matches) return;

      const minimumFrameTime = mobileQuery.matches ? 1000 / 24 : 1000 / 40;
      if (timestamp - lastPaint >= minimumFrameTime) {
        draw(timestamp);
        lastPaint = timestamp;
      }
      frame = requestAnimationFrame(animate);
    };

    const syncAnimation = () => {
      const shouldAnimate = !document.hidden && isIntersecting && !motionQuery.matches;
      if (shouldAnimate && frame === null) frame = requestAnimationFrame(animate);
      if (!shouldAnimate) {
        stop();
        draw(lastPaint || performance.now());
      }
    };

    const resize = () => {
      const bounds = root.getBoundingClientRect();
      width = Math.max(1, Math.round(bounds.width));
      height = Math.max(1, Math.round(bounds.height));
      const mobileCap = mobileQuery.matches ? 1.4 : dprLimit;
      const dpr = Math.min(window.devicePixelRatio || 1, mobileCap, dprLimit);
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      if (silkCanvas) {
        silkCanvas.width = Math.max(1, Math.round(width * Math.min(dpr, mobileQuery.matches ? .65 : 1)));
        silkCanvas.height = Math.max(1, Math.round(height * Math.min(dpr, mobileQuery.matches ? .65 : 1)));
      }
      draw(lastPaint || performance.now());
    };

    const intersectionObserver = new IntersectionObserver(
      ([entry]) => {
        isIntersecting = entry.isIntersecting;
        syncAnimation();
      },
      { rootMargin: "160px 0px", threshold: 0.01 },
    );
    const resizeObserver = new ResizeObserver(resize);
    const handleVisibility = () => syncAnimation();
    const handleMotionChange = () => syncAnimation();
    const handleMobileChange = () => {
      resize();
      syncAnimation();
    };

    intersectionObserver.observe(root);
    resizeObserver.observe(root);
    document.addEventListener("visibilitychange", handleVisibility);
    motionQuery.addEventListener("change", handleMotionChange);
    mobileQuery.addEventListener("change", handleMobileChange);
    resize();
    syncAnimation();

    return () => {
      stop();
      intersectionObserver.disconnect();
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", handleVisibility);
      motionQuery.removeEventListener("change", handleMotionChange);
      mobileQuery.removeEventListener("change", handleMobileChange);
      silk?.dispose();
    };
  }, [intensity, maxDpr, speed]);

  return (
    <div
      ref={rootRef}
      className={className ? `${styles.field} ${className}` : styles.field}
      aria-hidden="true"
    >
      <canvas ref={silkRef} className={styles.canvas} />
      <canvas ref={canvasRef} className={styles.canvas} />
      <span className={styles.prismaticVeil} />
    </div>
  );
}

export default OraktSignalField;
