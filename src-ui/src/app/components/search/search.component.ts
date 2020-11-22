import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { SearchHit } from 'src/app/data/search-result';
import { SearchService } from 'src/app/services/rest/search.service';

@Component({
  selector: 'app-search',
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.scss']
})
export class SearchComponent implements OnInit {
  
  results: SearchHit[] = []

  query: string = ""

  searching = false

  currentPage = 1

  pageCount = 1

  resultCount

  constructor(private searchService: SearchService, private route: ActivatedRoute) { }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(paramMap => {
      this.query = paramMap.get('query')
      this.searching = true
      this.currentPage = 1
      this.loadPage()
    })
    
  }

  loadPage(append: boolean = false) {
    this.searchService.search(this.query, this.currentPage).subscribe(result => {
      if (append) {
        this.results.push(...result.results)
      } else {
        this.results = result.results
      }
      this.pageCount = result.page_count
      this.searching = false
      this.resultCount = result.count
    })
  }

  onScroll() {
    console.log(this.currentPage)
    console.log(this.pageCount)
    if (this.currentPage < this.pageCount) {
      this.currentPage += 1
      this.loadPage(true)
    }
  }

}
