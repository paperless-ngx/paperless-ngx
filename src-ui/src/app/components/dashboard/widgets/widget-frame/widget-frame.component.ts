import { Component, EventEmitter, Input, Output } from '@angular/core'

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

  @Output()
  dndStart: EventEmitter<DragEvent> = new EventEmitter()

  @Output()
  dndMoved: EventEmitter<DragEvent> = new EventEmitter()

  @Output()
  dndCanceled: EventEmitter<DragEvent> = new EventEmitter()

  @Output()
  dndEnd: EventEmitter<DragEvent> = new EventEmitter()
}
