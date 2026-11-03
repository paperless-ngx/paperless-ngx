import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  inject,
  input,
} from '@angular/core'
import { icons } from './icons'

/** Converts icon name e.g. `arrow-down-up` to its registry key. */
const toKey = (name: string) =>
  name.trim().replace(/-(.)/g, (_, char: string) => char.toUpperCase())

/**
 * Renders an icon from the official bootstrap-icons package as inline SVG.
 * Icons must be registered in `./icons.ts`.
 */
@Component({
  selector: 'pngx-bs-icon',
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
      const element = this.elementRef.nativeElement
      element.innerHTML = this.svg()
      const svg = element.firstElementChild
      if (!svg) return
      const width = this.width()
      const height = this.height()
      if (width) svg.setAttribute('width', String(width))
      if (height) svg.setAttribute('height', String(height))
    })
  }

  private svg(): string {
    const name = this.name()
    if (!name) return ''
    const svg = icons[toKey(name)]
    if (!svg) {
      console.warn(`Icon not found: ${name}`)
      return ''
    }
    return svg
  }
}
