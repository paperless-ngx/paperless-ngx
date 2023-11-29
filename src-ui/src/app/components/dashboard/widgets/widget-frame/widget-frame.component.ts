import { Component, Input } from '@angular/core'

@Component({
  selector: 'pngx-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
})
export class WidgetFrameComponent {
  constructor() {}

  @Input()
  title: string

  @Input()
  loading: boolean = false

  @Input()
  draggable: any
}
