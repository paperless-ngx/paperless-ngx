
  function componentToHex(c) {
    var hex = c.toString(16);
    return hex.length == 1 ? "0" + hex : hex;
  }

  export function randomColor() {
    let r = Math.floor(Math.random() * 150) + 50
    let g = Math.floor(Math.random() * 150) + 50
    let b = Math.floor(Math.random() * 150) + 50
    return `#${componentToHex(r)}${componentToHex(g)}${componentToHex(b)}`
  }