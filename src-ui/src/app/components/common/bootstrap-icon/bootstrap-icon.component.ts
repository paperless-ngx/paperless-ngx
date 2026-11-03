import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  inject,
  input,
} from '@angular/core'
import { icons } from './icons'

const DEFAULT_SIZE = '16'

/** Converts icon name e.g. `arrow-down-up` to its registry key. */
const toKey = (name: string) =>
  name.trim().replace(/-(.)/g, (_, char: string) => char.toUpperCase())

/**
 * Renders an icon from the official bootstrap-icons package as inline SVG.
 * Icons must be registered in `./icons.ts`.
 */
@Component({
  // keep the selector of the ngx-bootstrap-icons
  // eslint-disable-next-line @angular-eslint/component-selector
  selector: 'i-bs',
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BootstrapIconComponent {
  private readonly elementRef = inject(ElementRef<HTMLElement>)

  readonly name = input<string>()
  readonly width = input<string | number>()
  readonly height = input<string | number>()

  constructor() {
    effect(() => {
      this.elementRef.nativeElement.innerHTML = this.svg()
    })
  }

  private svg(): string {
    const name = this.name()
    if (!name) return ''
    let svg = icons[toKey(name)]
    if (!svg) {
      console.warn(`Icon not found: ${name}`)
      return ''
    }
    const width = this.width()
    const height = this.height()
    if (width) {
      svg = svg.replace(`width="${DEFAULT_SIZE}"`, `width="${width}"`)
    }
    if (height) {
      svg = svg.replace(`height="${DEFAULT_SIZE}"`, `height="${height}"`)
    }
    return svg
  }
}
