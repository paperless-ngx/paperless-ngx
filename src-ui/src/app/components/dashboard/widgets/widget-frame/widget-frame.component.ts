import { DragDropModule } from '@angular/cdk/drag-drop'
import { NgTemplateOutlet } from '@angular/common'
import { AfterViewInit, Component, Input } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'

@Component({
  selector: 'pngx-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
  imports: [DragDropModule, NgxBootstrapIconsModule, NgTemplateOutlet],
})
export class WidgetFrameComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  constructor() {
    super()
  }

  @Input()
  title: string

  @Input()
  loading: boolean = false

  @Input()
  draggable: any

  @Input()
  cardless: boolean = false

  @Input()
  badge: string

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.show = true
    }, 100)
  }
}
