import { Component, Input, OnInit } from '@angular/core';
import { SearchHitHighlight } from 'src/app/data/search-result';

@Component({
  selector: 'app-result-highlight',
  templateUrl: './result-highlight.component.html',
  styleUrls: ['./result-highlight.component.scss']
})
export class ResultHighlightComponent implements OnInit {

  constructor() { }

  @Input()
  highlights: SearchHitHighlight[][]

  ngOnInit(): void {
  }

}
