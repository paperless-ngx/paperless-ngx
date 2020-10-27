import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { SearchResult, SearchService } from 'src/app/services/rest/search.service';

@Component({
  selector: 'app-search',
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.css']
})
export class SearchComponent implements OnInit {
  
  results: SearchResult[] = []

  query: string = ""

  constructor(private searchService: SearchService, private route: ActivatedRoute) { }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(paramMap => {
      this.query = paramMap.get('query')
      this.searchService.search(this.query).subscribe(result => {
        this.results = result
      })
    })
    
  }

}
