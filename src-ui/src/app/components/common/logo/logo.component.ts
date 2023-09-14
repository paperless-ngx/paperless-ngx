import { Component, Input } from '@angular/core'

@Component({
  selector: 'pngx-logo',
  templateUrl: './logo.component.html',
  styleUrls: ['./logo.component.scss'],
})
export class LogoComponent {
  @Input()
  extra_classes: string

  @Input()
  height = '6em'

  getClasses() {
    return ['logo'].concat(this.extra_classes).join(' ')
  }
}
