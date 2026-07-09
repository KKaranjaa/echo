/**
 * echo-background.js  v2
 * PixelBlast WebGL background — Three.js ES module, no build step.
 * Features: dithered pixel field, mouse gravity, click ripples, light/dark theme sync.
 */

import * as THREE from 'three';

// ─── Vertex shader ─────────────────────────────────────────────────────────
const VERTEX_SRC = `void main() { gl_Position = vec4(position, 1.0); }`;

// ─── Fragment shader ────────────────────────────────────────────────────────
const FRAGMENT_SRC = /* glsl */`
precision highp float;

uniform vec3  uColor;       // set per-theme
uniform float uAlpha;       // 0.45 dark / 0.28 light
uniform vec2  uResolution;
uniform float uTime;
uniform float uPixelSize;   // ECHO TUNED: 5.0
uniform float uScale;       // ECHO TUNED: 4.0
uniform float uDensity;     // ECHO TUNED: 0.82
uniform float uEdgeFade;    // ECHO TUNED: 0.35
uniform vec2  uMouse;       // normalised 0..1

const int MAX_CLICKS = 10;
uniform vec2  uClickPos[MAX_CLICKS];
uniform float uClickTimes[MAX_CLICKS];
uniform float uRippleSpeed;  // ECHO TUNED: 0.22
uniform float uRippleThick;  // ECHO TUNED: 0.07
uniform float uRippleIntens; // ECHO TUNED: 0.75

out vec4 fragColor;

// ── Bayer ordered dithering ─────────────────────────────────────────────────
float Bayer2(vec2 a) { a=floor(a); return fract(a.x/2.+a.y*a.y*.75); }
#define Bayer4(a) (Bayer2(.5*(a))*.25+Bayer2(a))
#define Bayer8(a) (Bayer4(.5*(a))*.25+Bayer2(a))

// ── Value noise ─────────────────────────────────────────────────────────────
float hash11(float n) { return fract(sin(n)*43758.5453); }

float vnoise(vec3 p) {
  vec3 ip=floor(p), fp=fract(p);
  float n000=hash11(dot(ip+vec3(0,0,0),vec3(1,57,113)));
  float n100=hash11(dot(ip+vec3(1,0,0),vec3(1,57,113)));
  float n010=hash11(dot(ip+vec3(0,1,0),vec3(1,57,113)));
  float n110=hash11(dot(ip+vec3(1,1,0),vec3(1,57,113)));
  float n001=hash11(dot(ip+vec3(0,0,1),vec3(1,57,113)));
  float n101=hash11(dot(ip+vec3(1,0,1),vec3(1,57,113)));
  float n011=hash11(dot(ip+vec3(0,1,1),vec3(1,57,113)));
  float n111=hash11(dot(ip+vec3(1,1,1),vec3(1,57,113)));
  vec3 w=fp*fp*fp*(fp*(fp*6.-15.)+10.);
  return mix(
    mix(mix(n000,n100,w.x),mix(n010,n110,w.x),w.y),
    mix(mix(n001,n101,w.x),mix(n011,n111,w.x),w.y),
    w.z
  )*2.-1.;
}

// ── FBM ─────────────────────────────────────────────────────────────────────
float fbm(vec2 uv, float t) {
  vec3 p=vec3(uv*uScale,t);
  float s=1.,a=1.,f=1.;
  for(int i=0;i<5;i++){ s+=a*vnoise(p*f); f*=1.25; a*=.9; }
  return s*.5+.5;
}

// ── Circle mask ──────────────────────────────────────────────────────────────
float circle(vec2 p, float cov) {
  float r=sqrt(cov)*.25;
  float d=length(p-.5)-r;
  float aa=.5*fwidth(d);
  return cov*(1.-smoothstep(-aa,aa,d*2.));
}

void main() {
  vec2 fc = gl_FragCoord.xy - uResolution*.5;
  float asp = uResolution.x / uResolution.y;

  vec2 puv = fract(fc / uPixelSize);
  vec2 cid = floor(fc / (8.*uPixelSize));
  vec2 uv  = cid * 8. * uPixelSize / uResolution * vec2(asp, 1.);

  // Subtle mouse gravity — pixels near cursor are nudged toward it
  vec2 mouseUV = (uMouse * uResolution - uResolution*.5) / uResolution * vec2(asp, 1.);
  float mouseDist = length(uv - mouseUV);
  float gravity = smoothstep(.30, 0., mouseDist) * 0.055;
  uv += normalize(mouseUV - uv + vec2(0.0001)) * gravity;

  float base = fbm(uv, uTime*.05)*.5 - .65;
  float feed = base + (uDensity - .5)*.3;

  // Click ripples
  for(int i=0; i<MAX_CLICKS; i++) {
    vec2 pos = uClickPos[i];
    if(pos.x < 0.) continue;
    vec2 cuv = ((pos - uResolution*.5) / uResolution) * vec2(asp, 1.);
    float t   = max(uTime - uClickTimes[i], 0.);
    float r   = distance(uv, cuv);
    float ring = exp(-pow((r - uRippleSpeed*t) / uRippleThick, 2.));
    float atten = exp(-1.*t) * exp(-8.*r);
    feed = max(feed, ring * atten * uRippleIntens);
  }

  float bayer = Bayer8(fc / uPixelSize) - .5;
  float bw = step(.5, feed + bayer);
  float M  = circle(puv, bw);

  // Edge vignette fade
  if(uEdgeFade > 0.) {
    vec2 norm = gl_FragCoord.xy / uResolution;
    float edge = min(min(norm.x, norm.y), min(1.-norm.x, 1.-norm.y));
    M *= smoothstep(0., uEdgeFade, edge);
  }

  // Linear → sRGB
  vec3 srgb = mix(
    uColor * 12.92,
    1.055 * pow(uColor, vec3(1./2.4)) - .055,
    step(.0031308, uColor)
  );

  fragColor = vec4(srgb, M * uAlpha);
}
`;

// ─── Theme palette ──────────────────────────────────────────────────────────
const THEME = {
  dark:  { color: new THREE.Color('#C084FC'), alpha: 0.45 },
  light: { color: new THREE.Color('#7C3AED'), alpha: 0.28 },
};

const MAX_CLICKS = 10;

/**
 * Initialise the PixelBlast WebGL background.
 * @param {string} containerId
 * @returns {() => void} cleanup function
 */
export function initEchoBackground(containerId = 'echo-bg') {
  const container = document.getElementById(containerId);
  if (!container) return () => {};

  // ── Renderer ─────────────────────────────────────────────────────────────
  const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearAlpha(0);
  Object.assign(renderer.domElement.style, {
    position: 'absolute',
    inset: '0',
    width: '100%',
    height: '100%',
  });
  container.appendChild(renderer.domElement);

  const dpr    = renderer.getPixelRatio();
  const scene  = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  // ── Uniforms ─────────────────────────────────────────────────────────────
  const uniforms = {
    uResolution:   { value: new THREE.Vector2() },
    uTime:         { value: 0 },
    uColor:        { value: THEME.dark.color.clone() },
    uAlpha:        { value: THEME.dark.alpha },
    uPixelSize:    { value: 5 * dpr },
    uScale:        { value: 4.0 },
    uDensity:      { value: 0.82 },
    uEdgeFade:     { value: 0.35 },
    uMouse:        { value: new THREE.Vector2(0.5, 0.5) },
    uClickPos:     { value: Array.from({ length: MAX_CLICKS }, () => new THREE.Vector2(-1, -1)) },
    uClickTimes:   { value: new Float32Array(MAX_CLICKS) },
    uRippleSpeed:  { value: 0.22 },
    uRippleThick:  { value: 0.07 },
    uRippleIntens: { value: 0.75 },
  };

  const material = new THREE.ShaderMaterial({
    vertexShader:   VERTEX_SRC,
    fragmentShader: FRAGMENT_SRC,
    uniforms,
    transparent: true,
    depthTest:   false,
    depthWrite:  false,
    glslVersion: THREE.GLSL3,
  });

  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  scene.add(quad);

  // ── Resize ────────────────────────────────────────────────────────────────
  const resize = () => {
    const w = container.clientWidth  || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    uniforms.uResolution.value.set(
      renderer.domElement.width,
      renderer.domElement.height,
    );
    uniforms.uPixelSize.value = 5 * dpr;
  };
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(container);

  // ── Mouse gravity ─────────────────────────────────────────────────────────
  const onMouseMove = e => {
    uniforms.uMouse.value.set(
      e.clientX / window.innerWidth,
      1 - e.clientY / window.innerHeight,
    );
  };
  window.addEventListener('mousemove', onMouseMove, { passive: true });

  // ── Click ripples ─────────────────────────────────────────────────────────
  let clickIx = 0;
  const onPointerDown = e => {
    const rect  = renderer.domElement.getBoundingClientRect();
    const sx    = renderer.domElement.width  / rect.width;
    const sy    = renderer.domElement.height / rect.height;
    uniforms.uClickPos.value[clickIx].set(
      (e.clientX - rect.left) * sx,
      (rect.height - (e.clientY - rect.top)) * sy,
    );
    uniforms.uClickTimes.value[clickIx] = uniforms.uTime.value;
    clickIx = (clickIx + 1) % MAX_CLICKS;
  };
  renderer.domElement.addEventListener('pointerdown', onPointerDown, { passive: true });

  // ── Theme sync via MutationObserver ───────────────────────────────────────
  const syncTheme = () => {
    const isDark = document.documentElement.classList.contains('dark');
    const t = isDark ? THEME.dark : THEME.light;
    uniforms.uColor.value.copy(t.color);
    uniforms.uAlpha.value = t.alpha;
  };
  syncTheme(); // initial
  const themeObs = new MutationObserver(syncTheme);
  themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  // ── Animation loop ────────────────────────────────────────────────────────
  const clock = new THREE.Clock();
  const SPEED = 0.25;   // ECHO TUNED: slow and academic
  const T0    = Math.random() * 1000;

  let raf;
  const animate = () => {
    uniforms.uTime.value = T0 + clock.getElapsedTime() * SPEED;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(animate);
  };
  raf = requestAnimationFrame(animate);

  // ── Cleanup ───────────────────────────────────────────────────────────────
  return () => {
    ro.disconnect();
    themeObs.disconnect();
    window.removeEventListener('mousemove', onMouseMove);
    cancelAnimationFrame(raf);
    quad.geometry.dispose();
    material.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    if (renderer.domElement.parentElement === container) {
      container.removeChild(renderer.domElement);
    }
  };
}
