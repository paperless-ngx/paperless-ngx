import { Component, OnInit } from '@angular/core'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'

@Component({
  selector: 'app-welcome-widget',
  templateUrl: './welcome-widget.component.html',
  styleUrls: ['./welcome-widget.component.scss'],
})
export class WelcomeWidgetComponent implements OnInit {
  constructor(public readonly tourService: TourService) {}

  ngOnInit(): void {}
}
