import { Component, EventEmitter, Output, inject } from '@angular/core'
import { NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { BrandMarkComponent } from '../../../common/logo/brand-mark/brand-mark.component'

@Component({
  selector: 'pngx-welcome-widget',
  templateUrl: './welcome-widget.component.html',
  styleUrls: ['./welcome-widget.component.scss'],
  imports: [NgbAlertModule, BrandMarkComponent],
})
export class WelcomeWidgetComponent {
  readonly tourService = inject(TourService)

  @Output()
  dismiss: EventEmitter<boolean> = new EventEmitter()
}
