// Pass 3: colour. colour = palette(fract(field + phase)); advancing the phase
// every frame is the original's AnimatePalette.
//
// Modern: the palette is sampled with textureGrad, so where bands get denser
// than a pixel the mip chain averages them (the hardware does the
// anti-aliasing). Classic: one of 256 entries, exactly as an indexed 8-bit
// screen would show it.
//
// Keep in step with FS_PALETTE in lab/electric-lab.html. (The lab has no
// uOrigin: it only ever draws one screen.)

uniform sampler2D uFieldA, uFieldB, uText;
uniform sampler2DArray uPal;
uniform vec2 uOrigin;    // where this view starts in the window (one per monitor)
uniform float uLayerA, uLayerB, uMix, uPhase, uShiftA, uShiftB;
uniform int uClassic, uBlurred;
out vec4 o;
const float TAU = 6.283185307179586;

ivec2 pixel() { return ivec2(gl_FragCoord.xy - uOrigin); }

vec3 shade(sampler2D field, float layer, float shift) {
    vec4 v = texelFetch(field, pixel(), 0);
    float coherence = 1.0;
    float u = v.r;
    if (uBlurred == 1) {
        u = atan(v.b, v.g) / TAU;
        coherence = smoothstep(0.05, 0.6, length(v.gb));
    }
    u += uPhase + shift;
    vec3 c;
    if (uClassic == 1) {
        int idx = int(floor(fract(u) * 256.0)) & 255;
        c = texelFetch(uPal, ivec3(idx, 0, int(layer)), 0).rgb;
    } else {
        vec2 du = vec2(dFdx(u), dFdy(u));
        du -= floor(du + 0.5);                        // ignore jumps of a whole cycle
        c = textureGrad(uPal, vec3(fract(u), 0.5, layer), vec2(du.x, 0.0), vec2(du.y, 0.0)).rgb;
    }
    vec3 avg = textureLod(uPal, vec3(0.5, 0.5, layer), 8.0).rgb;
    return mix(avg, c, coherence);
}

void main() {
    float mask = texelFetch(uText, pixel(), 0).r;
    vec3 a = shade(uFieldA, uLayerA, mask * uShiftA);
    vec3 c = a;
    if (uMix > 0.0) c = mix(a, shade(uFieldB, uLayerB, mask * uShiftB), uMix);
    o = vec4(c, 1.0);
}
