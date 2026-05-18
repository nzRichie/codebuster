/**
 * Fixed-size FIFO buffer; overwriting oldest when full.
 */

export class RingBuffer {
  constructor(capacity) {
    if (capacity < 1) {
      throw new RangeError("capacity must be >= 1");
    }
    this._capacity = capacity;
    this._items = [];
  }

  push(value) {
    if (this._items.length >= this._capacity) {
      this._items.shift();
    }
    this._items.push(value);
  }

  values() {
    return [...this._items];
  }
}
