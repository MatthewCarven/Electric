// Scales a low-resolution frame (Half, or the 1997 640x480 mode) up to the
// screen with hard pixel edges.

uniform sampler2D uFrame;
uniform vec2 uOrigin;    // where this view starts in the window
uniform vec2 uScreen;    // the view's size on screen
out vec4 o;

void main() {
    o = texture(uFrame, (gl_FragCoord.xy - uOrigin) / uScreen);
}
