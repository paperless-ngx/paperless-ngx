import { Component, Input, OnInit } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';

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

}
