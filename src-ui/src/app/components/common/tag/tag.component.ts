import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { TAG_COLOURS, PaperlessTag } from 'src/app/data/paperless-tag';

@Component({
  selector: 'app-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.scss']
})
export class TagComponent implements OnInit {

  constructor() { }

  @Input()
  tag: PaperlessTag

  @Input()
  clickable: boolean = false

  ngOnInit(): void {
  }

  getColour() {
    return TAG_COLOURS.find(c => c.id == this.tag.colour)
  }

}
