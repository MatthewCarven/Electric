// Pass 2 (optional): one direction of a separable gaussian. The palette pass
// reads the blurred (cos, sin) pair back as a circular mean, so bands soften
// instead of smearing across the palette's wrap point, and the dense
// shimmering cores fade to the palette's mean colour.
//
// Keep in step with FS_BLUR in lab/electric-lab.html.

uniform sampler2D uTex;
uniform vec2 uDir;
uniform float uSigma;
out vec4 o;

void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 hi = textureSize(uTex, 0) - 1;
    int R = int(ceil(uSigma * 2.5));
    vec4 acc = vec4(0.0);
    float wsum = 0.0;
    for (int i = -64; i <= 64; i++) {             // sigma up to 25
        if (i < -R || i > R) continue;
        float w = exp(-0.5 * float(i * i) / (uSigma * uSigma));
        acc += w * texelFetch(uTex, clamp(p + ivec2(uDir) * i, ivec2(0), hi), 0);
        wsum += w;
    }
    o = acc / wsum;
}
