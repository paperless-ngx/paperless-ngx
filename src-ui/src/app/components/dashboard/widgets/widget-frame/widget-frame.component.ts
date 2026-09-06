import { DragDropModule } from '@angular/cdk/drag-drop'
import { NgTemplateOutlet } from '@angular/common'
import { AfterViewInit, Component, input, signal } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'

@Component({
  selector: 'pngx-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
  imports: [DragDropModule, NgxBootstrapIconsModule, NgTemplateOutlet],
})
export class WidgetFrameComponent implements AfterViewInit {
  readonly show = signal(false)

  loading = input(false)

  title = input<string>()

  titleIcon = input<string>()

  draggable = input<any>()

  cardless = input(false)

  badge = input<string | number>(null)

  ngAfterViewInit(): void {
    this.show.set(true)
  }
}
