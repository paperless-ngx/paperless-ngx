import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { SearchHit } from 'src/app/data/search-result';
import { DocumentService } from 'src/app/services/rest/document.service';
import { SearchService } from 'src/app/services/rest/search.service';

@Component({
  selector: 'app-search',
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.scss']
})
export class SearchComponent implements OnInit {

  results: SearchHit[] = []

  query: string = ""

  more_like: number

  more_like_doc: PaperlessDocument

  searching = false

  currentPage = 1

  pageCount = 1

  resultCount

  correctedQuery: string = null

  errorMessage: string

  get maxScore() {
    return this.results?.length > 0 ? this.results[0].score : 100
  }

  constructor(private searchService: SearchService, private route: ActivatedRoute, private router: Router, private documentService: DocumentService) { }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(paramMap => {
      window.scrollTo(0, 0)
      this.query = paramMap.get('query')
      this.more_like = paramMap.has('more_like') ? +paramMap.get('more_like') : null
      if (this.more_like) {
        this.documentService.get(this.more_like).subscribe(r => {
          this.more_like_doc = r
        })
      } else {
        this.more_like_doc = null
      }
      this.searching = true
      this.currentPage = 1
      this.loadPage()
    })

  }

  searchCorrectedQuery() {
    this.router.navigate(["search"], {queryParams: {query: this.correctedQuery, more_like: this.more_like}})
  }

  loadPage(append: boolean = false) {
    this.errorMessage = null
    this.correctedQuery = null

    this.searchService.search(this.query, this.currentPage, this.more_like).subscribe(result => {
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
