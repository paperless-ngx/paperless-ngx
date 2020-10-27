import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';

@Component({
  selector: 'app-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.css']
})
export class TagComponent implements OnInit {

  constructor() { }

  @Input()
  tag: PaperlessTag

  @Input()
  clickable: boolean = false

  @Output()
  click = new EventEmitter()

  ngOnInit(): void {
  }

  getColour() {
    return PaperlessTag.COLOURS.find(c => c.id == this.tag.colour)
  }

}
