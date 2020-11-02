import { Component, Input, OnInit } from '@angular/core';
import { SearchHitHighlight } from 'src/app/data/search-result';

@Component({
  selector: 'app-result-hightlight',
  templateUrl: './result-hightlight.component.html',
  styleUrls: ['./result-hightlight.component.css']
})
export class ResultHightlightComponent implements OnInit {

  constructor() { }

  @Input()
  highlights: SearchHitHighlight[][]

  ngOnInit(): void {
  }

}
