import { Component, input } from '@angular/core'

@Component({
  selector: 'pngx-brand-mark',
  templateUrl: './brand-mark.component.html',
  host: {
    '[style.width]': 'width()',
    '[style.height]': 'height()',
  },
})
export class BrandMarkComponent {
  readonly width = input<string>(null)
  readonly height = input<string>(null)
}
