import { Component, Input } from '@angular/core'
import { PaperlessTag } from 'src/app/data/paperless-tag'

@Component({
  selector: 'pngx-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.scss'],
})
export class TagComponent {
  constructor() {}

  @Input()
  tag: PaperlessTag

  @Input()
  linkTitle: string = ''

  @Input()
  clickable: boolean = false
}
