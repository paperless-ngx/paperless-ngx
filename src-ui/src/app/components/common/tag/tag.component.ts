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
  linkTitle: string = ""

  @Input()
  clickable: boolean = false

  ngOnInit(): void {
  }

  getColour() {
    var color = TAG_COLOURS.find(c => c.id == this.tag.colour)
    if (color) {
      return color
    }
    return { id: this.tag.colour, name: this.tag.colour, textColor: "#ffffff" }
  }

}
