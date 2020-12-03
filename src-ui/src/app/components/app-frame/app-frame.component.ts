import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { from, Observable, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { SearchService } from 'src/app/services/rest/search.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { DocumentDetailComponent } from '../document-detail/document-detail.component';
  
@Component({
  selector: 'app-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss']
})
export class AppFrameComponent implements OnInit, OnDestroy {

  constructor (
    public router: Router,
    private activatedRoute: ActivatedRoute,
    private openDocumentsService: OpenDocumentsService,
    private searchService: SearchService,
    public viewConfigService: SavedViewConfigService
    ) {
  }

  isMenuCollapsed: boolean = true

  closeMenu() {
    this.isMenuCollapsed = true
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
    this.closeMenu()
    this.router.navigate(['search'], {queryParams: {query: this.searchField.value}})
  }

  closeAll() {
    this.closeMenu()
    this.openDocumentsService.closeAll()

    // TODO: is there a better way to do this?
    let route = this.activatedRoute
    while (route.firstChild) {
      route = route.firstChild
    }
    if (route.component == DocumentDetailComponent) {
      this.router.navigate([""])
    }
  }

  ngOnInit() {
    this.openDocuments = this.openDocumentsService.getOpenDocuments()
  }

  ngOnDestroy() {
    if (this.openDocumentsSubscription) {
      this.openDocumentsSubscription.unsubscribe()
    }
  }

}
