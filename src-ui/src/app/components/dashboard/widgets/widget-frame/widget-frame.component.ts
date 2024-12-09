import { AfterViewInit, Component, Input } from '@angular/core'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'

@Component({
  selector: 'pngx-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss'],
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

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.show = true
    }, 100)
  }
}
