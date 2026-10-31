// Pass 1: the field. The modern equivalent of the original's 256-colour
// indexed image, computed per pixel in float.
//
// Each particle contributes (scalable, fixed): the first part is multiplied by
// band density; the second is an angle term with a whole number of windings,
// left unscaled so its seam stays a whole palette cycle (and invisible).
//
// Keep in step with FS_FIELD in lab/electric-lab.html.

#define MAXP 16
uniform vec2 uRes;
uniform int uCount;
uniform vec4 uP[MAXP];   // x, y, signed strength, type
uniform vec4 uQ[MAXP];   // per-type parameters; w = rotation
uniform int uTile;       // 0 normal, 1 tiling (2x2 mirrored), 2 dissymmetric (2x2 repeated)
uniform float uDensity;
out vec4 o;
const float TAU = 6.283185307179586;

vec2 pot(vec2 d, vec4 p, vec4 q) {
    int type = int(p.w + 0.5);
    float s = p.z;
    float r2 = max(dot(d, d), 1e-9);
    float r = sqrt(r2);
    float a = atan(d.y, d.x);
    if (type == 1) return vec2(s * q.x / (r2 + q.y), 0.0);                 // Electrons: 1/r^2
    if (type == 2) return vec2(s * q.y * sin(r * q.x + q.w), 0.0);         // Melons: sin(r)
    if (type == 3) return vec2(s * q.x * r, 0.0);                          // Dindons: r
    if (type == 4) return vec2(s * q.x * r, s * q.y * a / TAU);            // Cochons: spiral
    if (type == 5) return vec2(s * q.y * sin(q.x * a + q.w), 0.0);         // Croutons: sin(angle)
    if (type == 6) { float z = 1.0 + r2 / (q.y * q.y);                     // Jambons: Cauchy-Lorentz^3
                     return vec2(s * q.x / (z * z * z), 0.0); }
    if (type == 7) return vec2(0.0, s * q.x * a / TAU);                    // Cornichons: angle
    return vec2(s * q.x * log(r), s * q.y * a / TAU);                      // Oignons: log spiral
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;   // height spans -0.5..0.5
    vec2 h = vec2(0.5 * uRes.x / uRes.y, 0.5);           // half extents
    if (uTile == 1) uv = (abs(uv) - 0.5 * h) * 2.0;
    else if (uTile == 2) uv = (mod(uv + h, h) - 0.5 * h) * 2.0;
    vec2 v = vec2(0.0);
    for (int i = 0; i < MAXP; i++) {
        if (i >= uCount) break;
        v += pot(uv - uP[i].xy, uP[i], uQ[i]);
    }
    float u = v.x * uDensity + v.y;                      // in palette cycles
    o = vec4(u, cos(TAU * u), sin(TAU * u), 1.0);
}
