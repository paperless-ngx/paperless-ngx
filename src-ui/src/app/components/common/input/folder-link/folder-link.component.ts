import { Component, forwardRef, Input } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => FolderLinkComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-folder-link',
  templateUrl: './folder-link.component.html',
  styleUrls: ['./folder-link.component.scss'],
})
export class FolderLinkComponent extends AbstractInputComponent<string> {
  constructor() {
    super()
  }

  @Input()
  link: string
}
