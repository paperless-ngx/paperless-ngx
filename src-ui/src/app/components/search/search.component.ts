import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
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

  correctedQuery: string = null

  errorMessage: string

  constructor(private searchService: SearchService, private route: ActivatedRoute, private router: Router) { }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(paramMap => {
      this.query = paramMap.get('query')
      this.searching = true
      this.currentPage = 1
      this.loadPage()
    })

  }

  searchCorrectedQuery() {
    this.router.navigate(["search"], {queryParams: {query: this.correctedQuery}})
  }

  loadPage(append: boolean = false) {
    this.errorMessage = null
    this.correctedQuery = null
    this.searchService.search(this.query, this.currentPage).subscribe(result => {
      if (append) {
        this.results.push(...result.results)
      } else {
        this.results = result.results
      }
      this.pageCount = result.page_count
      this.searching = false
      this.resultCount = result.count
      this.correctedQuery = result.corrected_query
    }, error => {
      this.searching = false
      this.resultCount = 1
      this.pageCount = 1
      this.results = []
      this.errorMessage = error.error
    })
  }

  onScroll() {
    if (this.currentPage < this.pageCount) {
      this.currentPage += 1
      this.loadPage(true)
    }
  }

}
