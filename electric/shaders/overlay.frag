// The settings panel: a pygame surface blended over the picture.

uniform sampler2D uTex;
uniform vec2 uOrigin;
uniform vec2 uSize;
out vec4 o;

void main() {
    o = texture(uTex, (gl_FragCoord.xy - uOrigin) / uSize);
}
