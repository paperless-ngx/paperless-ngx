import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { from, Observable, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { SearchService } from 'src/app/services/rest/search.service';
import { environment } from 'src/environments/environment';
import { DocumentDetailComponent } from '../document-detail/document-detail.component';
import { Meta } from '@angular/platform-browser';

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
    this.router.navigate(['search'], {queryParams: {query: this.searchField.value}})
  }

  closeDocument(d: PaperlessDocument) {
    this.closeMenu()
    this.openDocumentsService.closeDocument(d)

    // TODO: is there a better way to do this? (taken from closeAll)
    let route = this.activatedRoute
    while (route.firstChild) {
      route = route.firstChild
    }
    if (route.component == DocumentDetailComponent) {
      this.router.navigate([""])
    }
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
