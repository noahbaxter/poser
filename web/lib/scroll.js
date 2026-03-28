// macOS swaps deltaY→deltaX when shift is held. Use whichever axis has movement.
export function scrollDelta(e) {
    return e.deltaY !== 0 ? e.deltaY : e.deltaX;
}
