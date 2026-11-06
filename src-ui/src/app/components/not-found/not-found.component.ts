import { Component } from '@angular/core'
import { RouterModule } from '@angular/router'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { LogoComponent } from '../common/logo/logo.component'

@Component({
  selector: 'pngx-not-found',
  templateUrl: './not-found.component.html',
  styleUrls: ['./not-found.component.scss'],
  imports: [LogoComponent, BootstrapIconComponent, RouterModule],
})
export class NotFoundComponent {
  constructor() {}
}
