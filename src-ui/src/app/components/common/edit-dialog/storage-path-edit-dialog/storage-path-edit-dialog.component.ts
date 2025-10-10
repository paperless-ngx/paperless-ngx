import { AsyncPipe, NgTemplateOutlet } from '@angular/common'
import { Component, OnDestroy, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAccordionModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent } from '@ng-select/ng-select'
import {
  Observable,
  Subject,
  catchError,
  concat,
  distinctUntilChanged,
  filter,
  map,
  of,
  switchMap,
  takeUntil,
  tap,
} from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Document } from 'src/app/data/document'
import { FILTER_TITLE } from 'src/app/data/filter-rule-type'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { StoragePath } from 'src/app/data/storage-path'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { DocumentService } from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { TextAreaComponent } from '../../input/textarea/textarea.component'

@Component({
  selector: 'pngx-storage-path-edit-dialog',
  templateUrl: './storage-path-edit-dialog.component.html',
  styleUrls: ['./storage-path-edit-dialog.component.scss'],
  imports: [
    SelectComponent,
    TextAreaComponent,
    TextComponent,
    CheckComponent,
    PermissionsFormComponent,
    IfOwnerDirective,
    AsyncPipe,
    NgTemplateOutlet,
    FormsModule,
    ReactiveFormsModule,
    NgbAccordionModule,
    NgSelectComponent,
  ],
})
export class StoragePathEditDialogComponent
  extends EditDialogComponent<StoragePath>
  implements OnDestroy
{
  private documentsService = inject(DocumentService)

  public documentsInput$ = new Subject<string>()
  public foundDocuments$: Observable<Document[]>
  private testDocument: Document
  public testResult: string
  public testFailed: boolean = false
  public loading = false
  public testLoading = false

  constructor() {
    super()
    this.service = inject(StoragePathService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
    this.initPathObservables()
  }

  getCreateTitle() {
    return $localize`Create new storage path`
  }

  getEditTitle() {
    return $localize`Edit storage path`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      path: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }

  public testPath(document: Document) {
    if (!document) {
      this.testResult = null
      return
    }
    this.testDocument = document
    this.testLoading = true
    ;(this.service as StoragePathService)
      .testPath(this.objectForm.get('path').value, document.id)
      .subscribe((result) => {
        if (result?.length) {
          this.testResult = result
          this.testFailed = false
        } else {
          this.testResult = null
          this.testFailed = true
        }
        this.testLoading = false
      })
  }

  compareDocuments(document: Document, selectedDocument: Document) {
    return document.id === selectedDocument.id
  }

  private initPathObservables() {
    this.objectForm
      .get('path')
      .valueChanges.pipe(
        takeUntil(this.unsubscribeNotifier),
        filter((path) => path && !!this.testDocument)
      )
      .subscribe(() => {
        this.testPath(this.testDocument)
      })

    this.foundDocuments$ = concat(
      of([]), // default items
      this.documentsInput$.pipe(
        distinctUntilChanged(),
        takeUntil(this.unsubscribeNotifier),
        tap(() => (this.loading = true)),
        switchMap((title) =>
          this.documentsService
            .listFiltered(
              1,
              null,
              'created',
              true,
              [{ rule_type: FILTER_TITLE, value: title }],
              { truncate_content: true }
            )
            .pipe(
              map((result) => result.results),
              catchError(() => of([])), // empty on error
              tap(() => (this.loading = false))
            )
        )
      )
    )
  }

  trackByFn(item: Document) {
    return item.id
  }
}
