import { Component } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { LogoComponent } from '../common/logo/logo.component'

@Component({
  selector: 'pngx-not-found',
  templateUrl: './not-found.component.html',
  styleUrls: ['./not-found.component.scss'],
  imports: [LogoComponent, NgxBootstrapIconsModule],
})
export class NotFoundComponent {
  constructor() {}
}
