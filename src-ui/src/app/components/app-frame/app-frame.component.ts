import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { ActivatedRoute, Router, Params } from '@angular/router';
import { from, Observable, Subscription, BehaviorSubject } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { SearchService } from 'src/app/services/rest/search.service';
import { environment } from 'src/environments/environment';
import { DocumentDetailComponent } from '../document-detail/document-detail.component';
import { Meta } from '@angular/platform-browser';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { FILTER_FULLTEXT_QUERY } from 'src/app/data/filter-rule-type';

@Component({
  selector: 'app-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss']
})
export class AppFrameComponent implements OnInit {

  constructor (
    public router: Router,
    private activatedRoute: ActivatedRoute,
    private openDocumentsService: OpenDocumentsService,
    private searchService: SearchService,
    public savedViewService: SavedViewService,
    private list: DocumentListViewService,
    private meta: Meta
    ) {

  }

  versionString = `${environment.appTitle} ${environment.version}`

  isMenuCollapsed: boolean = true

  closeMenu() {
    this.isMenuCollapsed = true
  }

  searchField = new FormControl('')

  get openDocuments(): PaperlessDocument[] {
    return this.openDocumentsService.getOpenDocuments()
  }

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
    this.list.quickFilter([{rule_type: FILTER_FULLTEXT_QUERY, value: this.searchField.value}])
  }

  closeDocument(d: PaperlessDocument) {
    this.closeMenu()
    this.openDocumentsService.closeDocument(d)

    let route = this.activatedRoute.snapshot
    while (route.firstChild) {
      route = route.firstChild
    }
    if (route.component == DocumentDetailComponent && route.params['id'] == d.id) {
      this.router.navigate([""])
    }
  }

  closeAll() {
    this.closeMenu()
    this.openDocumentsService.closeAll()

    let route = this.activatedRoute.snapshot
    while (route.firstChild) {
      route = route.firstChild
    }
    if (route.component == DocumentDetailComponent) {
      this.router.navigate([""])
    }
  }

  ngOnInit() {
  }

  get displayName() {
    // TODO: taken from dashboard component, is this the best way to pass around username?
    let tagFullName = this.meta.getTag('name=full_name')
    let tagUsername = this.meta.getTag('name=username')
    if (tagFullName && tagFullName.content) {
      return tagFullName.content
    } else if (tagUsername && tagUsername.content) {
      return tagUsername.content
    } else {
      return null
    }
  }

}
