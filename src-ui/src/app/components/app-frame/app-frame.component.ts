import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { Router } from '@angular/router';
import { from, Observable, of, scheduled, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { AuthService } from 'src/app/services/auth.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { SearchService } from 'src/app/services/rest/search.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
  
@Component({
  selector: 'app-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.css']
})
export class AppFrameComponent implements OnInit, OnDestroy {

  constructor (
    public router: Router,
    private openDocumentsService: OpenDocumentsService,
    private authService: AuthService,
    private searchService: SearchService,
    public viewConfigService: SavedViewConfigService
    ) {
  }

  searchField = new FormControl('')

  openDocuments: PaperlessDocument[] = []

  openDocumentsSubscription: Subscription

  searchAutoComplete = (text$: Observable<string>) =>
    text$.pipe(
      debounceTime(200),
      distinctUntilChanged(),
      map(term => {
        if (term.lastIndexOf(' ') != -1) {
          return term.substring(term.lastIndexOf(' ') + 1)
        } else {
          return term
        }
      }),
      switchMap(term =>
        term.length < 2 ? from([[]]) : this.searchService.autocomplete(term)
      )
    )
  
  itemSelected(event) {
    event.preventDefault()
    let currentSearch: string = this.searchField.value
    let lastSpaceIndex = currentSearch.lastIndexOf(' ')
    if (lastSpaceIndex != -1) {
      currentSearch = currentSearch.substring(0, lastSpaceIndex + 1)
      currentSearch += event.item + " "
    } else {
      currentSearch = event.item + " "
    }
    this.searchField.patchValue(currentSearch)
  }

  search() {
    this.router.navigate(['search'], {queryParams: {query: this.searchField.value}})
  }

  logout() {
    this.authService.logout()
  }

  ngOnInit() {
    this.openDocumentsSubscription = this.openDocumentsService.getOpenDocuments().subscribe(docs => this.openDocuments = docs)
  }

  ngOnDestroy() {
    this.openDocumentsSubscription.unsubscribe()
  }

}
