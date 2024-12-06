import { AfterViewInit, Component, Input } from '@angular/core'

@Component({
  selector: 'pngx-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
})
export class WidgetFrameComponent implements AfterViewInit {
  constructor() {}

  @Input()
  title: string

  @Input()
  loading: boolean = false

  @Input()
  draggable: any

  public reveal: boolean = false

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.reveal = true
    }, 100)
  }
}
