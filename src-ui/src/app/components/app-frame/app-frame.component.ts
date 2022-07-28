import { Component } from '@angular/core'
import { FormControl } from '@angular/forms'
import { ActivatedRoute, Router, Params } from '@angular/router'
import { from, Observable } from 'rxjs'
import {
  debounceTime,
  distinctUntilChanged,
  map,
  switchMap,
  first,
} from 'rxjs/operators'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SearchService } from 'src/app/services/rest/search.service'
import { environment } from 'src/environments/environment'
import { DocumentDetailComponent } from '../document-detail/document-detail.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_FULLTEXT_QUERY } from 'src/app/data/filter-rule-type'
import {
  RemoteVersionService,
  AppRemoteVersion,
} from 'src/app/services/rest/remote-version.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TasksService } from 'src/app/services/tasks.service'

@Component({
  selector: 'app-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.scss'],
})
export class AppFrameComponent {
  constructor(
    public router: Router,
    private activatedRoute: ActivatedRoute,
    private openDocumentsService: OpenDocumentsService,
    private searchService: SearchService,
    public savedViewService: SavedViewService,
    private remoteVersionService: RemoteVersionService,
    private list: DocumentListViewService,
    public settingsService: SettingsService,
    public tasksService: TasksService
  ) {
    this.remoteVersionService
      .checkForUpdates()
      .subscribe((appRemoteVersion: AppRemoteVersion) => {
        this.appRemoteVersion = appRemoteVersion
      })
    tasksService.reload()
  }

  versionString = `${environment.appTitle} ${environment.version}`
  appRemoteVersion

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
      map((term) => {
        if (term.lastIndexOf(' ') != -1) {
          return term.substring(term.lastIndexOf(' ') + 1)
        } else {
          return term
        }
      }),
      switchMap((term) =>
        term.length < 2 ? from([[]]) : this.searchService.autocomplete(term)
      )
    )

  itemSelected(event) {
    event.preventDefault()
    let currentSearch: string = this.searchField.value
    let lastSpaceIndex = currentSearch.lastIndexOf(' ')
    if (lastSpaceIndex != -1) {
      currentSearch = currentSearch.substring(0, lastSpaceIndex + 1)
      currentSearch += event.item + ' '
    } else {
      currentSearch = event.item + ' '
    }
    this.searchField.patchValue(currentSearch)
  }

  search() {
    this.closeMenu()
    this.list.quickFilter([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: (this.searchField.value as string).trim(),
      },
    ])
  }

  closeDocument(d: PaperlessDocument) {
    this.openDocumentsService
      .closeDocument(d)
      .pipe(first())
      .subscribe((confirmed) => {
        if (confirmed) {
          this.closeMenu()
          let route = this.activatedRoute.snapshot
          while (route.firstChild) {
            route = route.firstChild
          }
          if (
            route.component == DocumentDetailComponent &&
            route.params['id'] == d.id
          ) {
            this.router.navigate([''])
          }
        }
      })
  }

  closeAll() {
    // user may need to confirm losing unsaved changes
    this.openDocumentsService
      .closeAll()
      .pipe(first())
      .subscribe((confirmed) => {
        if (confirmed) {
          this.closeMenu()

          // TODO: is there a better way to do this?
          let route = this.activatedRoute
          while (route.firstChild) {
            route = route.firstChild
          }
          if (route.component === DocumentDetailComponent) {
            this.router.navigate([''])
          }
        }
      })
  }
}
