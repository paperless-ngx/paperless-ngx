import { Component, Input } from '@angular/core'

@Component({
  selector: 'app-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
})
export class WidgetFrameComponent {
  constructor() {}

  @Input()
  title: string

  @Input()
  loading: boolean = false
}
