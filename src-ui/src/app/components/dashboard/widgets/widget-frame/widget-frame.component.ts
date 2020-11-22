import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'app-widget-frame',
  templateUrl: './widget-frame.component.html',
  styleUrls: ['./widget-frame.component.scss']
})
export class WidgetFrameComponent implements OnInit {

  constructor() { }

  @Input()
  title: string

  ngOnInit(): void {
  }

}
