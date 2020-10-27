import { Component, Input, OnInit } from '@angular/core';
import { SearchResultHighlightedText } from 'src/app/services/rest/search.service';

@Component({
  selector: 'app-result-hightlight',
  templateUrl: './result-hightlight.component.html',
  styleUrls: ['./result-hightlight.component.css']
})
export class ResultHightlightComponent implements OnInit {

  constructor() { }

  @Input()
  highlights: SearchResultHighlightedText[][]

  ngOnInit(): void {
  }

}
