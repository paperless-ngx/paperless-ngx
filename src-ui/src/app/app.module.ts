import { BrowserModule } from '@angular/platform-browser'
import { APP_INITIALIZER, NgModule } from '@angular/core'
import { AppRoutingModule } from './app-routing.module'
import { AppComponent } from './app.component'
import {
  NgbDateAdapter,
  NgbDateParserFormatter,
  NgbModule,
} from '@ng-bootstrap/ng-bootstrap'
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http'
import { DocumentListComponent } from './components/document-list/document-list.component'
import { DocumentDetailComponent } from './components/document-detail/document-detail.component'
import { DashboardComponent } from './components/dashboard/dashboard.component'
import { TagListComponent } from './components/manage/tag-list/tag-list.component'
import { DocumentTypeListComponent } from './components/manage/document-type-list/document-type-list.component'
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component'
import { LogsComponent } from './components/admin/logs/logs.component'
import { SettingsComponent } from './components/admin/settings/settings.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { DatePipe, registerLocaleData } from '@angular/common'
import { NotFoundComponent } from './components/not-found/not-found.component'
import { ConfirmDialogComponent } from './components/common/confirm-dialog/confirm-dialog.component'
import { CorrespondentEditDialogComponent } from './components/common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { TagEditDialogComponent } from './components/common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from './components/common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { TagComponent } from './components/common/tag/tag.component'
import { ClearableBadgeComponent } from './components/common/clearable-badge/clearable-badge.component'
import { PageHeaderComponent } from './components/common/page-header/page-header.component'
import { AppFrameComponent } from './components/app-frame/app-frame.component'
import { ToastsComponent } from './components/common/toasts/toasts.component'
import { FilterEditorComponent } from './components/document-list/filter-editor/filter-editor.component'
import { FilterableDropdownComponent } from './components/common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableDropdownButtonComponent } from './components/common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import { DatesDropdownComponent } from './components/common/dates-dropdown/dates-dropdown.component'
import { DocumentCardLargeComponent } from './components/document-list/document-card-large/document-card-large.component'
import { DocumentCardSmallComponent } from './components/document-list/document-card-small/document-card-small.component'
import { BulkEditorComponent } from './components/document-list/bulk-editor/bulk-editor.component'
import { NgxFileDropModule } from 'ngx-file-drop'
import { TextComponent } from './components/common/input/text/text.component'
import { SelectComponent } from './components/common/input/select/select.component'
import { CheckComponent } from './components/common/input/check/check.component'
import { UrlComponent } from './components/common/input/url/url.component'
import { PasswordComponent } from './components/common/input/password/password.component'
import { SaveViewConfigDialogComponent } from './components/document-list/save-view-config-dialog/save-view-config-dialog.component'
import { TagsComponent } from './components/common/input/tags/tags.component'
import { IfPermissionsDirective } from './directives/if-permissions.directive'
import { SortableDirective } from './directives/sortable.directive'
import { CookieService } from 'ngx-cookie-service'
import { CsrfInterceptor } from './interceptors/csrf.interceptor'
import { SavedViewWidgetComponent } from './components/dashboard/widgets/saved-view-widget/saved-view-widget.component'
import { StatisticsWidgetComponent } from './components/dashboard/widgets/statistics-widget/statistics-widget.component'
import { UploadFileWidgetComponent } from './components/dashboard/widgets/upload-file-widget/upload-file-widget.component'
import { WidgetFrameComponent } from './components/dashboard/widgets/widget-frame/widget-frame.component'
import { WelcomeWidgetComponent } from './components/dashboard/widgets/welcome-widget/welcome-widget.component'
import { YesNoPipe } from './pipes/yes-no.pipe'
import { FileSizePipe } from './pipes/file-size.pipe'
import { FilterPipe } from './pipes/filter.pipe'
import { DocumentTitlePipe } from './pipes/document-title.pipe'
import { MetadataCollapseComponent } from './components/document-detail/metadata-collapse/metadata-collapse.component'
import { SelectDialogComponent } from './components/common/select-dialog/select-dialog.component'
import { NgSelectModule } from '@ng-select/ng-select'
import { NumberComponent } from './components/common/input/number/number.component'
import { SafeUrlPipe } from './pipes/safeurl.pipe'
import { SafeHtmlPipe } from './pipes/safehtml.pipe'
import { CustomDatePipe } from './pipes/custom-date.pipe'
import { DateComponent } from './components/common/input/date/date.component'
import { ISODateAdapter } from './utils/ngb-iso-date-adapter'
import { LocalizedDateParserFormatter } from './utils/ngb-date-parser-formatter'
import { ApiVersionInterceptor } from './interceptors/api-version.interceptor'
import { ColorSliderModule } from 'ngx-color/slider'
import { ColorComponent } from './components/common/input/color/color.component'
import { DocumentAsnComponent } from './components/document-asn/document-asn.component'
import { DocumentNotesComponent } from './components/document-notes/document-notes.component'
import { PermissionsGuard } from './guards/permissions.guard'
import { DirtyDocGuard } from './guards/dirty-doc.guard'
import { DirtySavedViewGuard } from './guards/dirty-saved-view.guard'
import { StoragePathListComponent } from './components/manage/storage-path-list/storage-path-list.component'
import { StoragePathEditDialogComponent } from './components/common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { SettingsService } from './services/settings.service'
import { TasksComponent } from './components/admin/tasks/tasks.component'
import { TourNgBootstrapModule } from 'ngx-ui-tour-ng-bootstrap'
import { UserEditDialogComponent } from './components/common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { GroupEditDialogComponent } from './components/common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { PermissionsSelectComponent } from './components/common/permissions-select/permissions-select.component'
import { MailAccountEditDialogComponent } from './components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { MailRuleEditDialogComponent } from './components/common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { PermissionsUserComponent } from './components/common/input/permissions/permissions-user/permissions-user.component'
import { PermissionsGroupComponent } from './components/common/input/permissions/permissions-group/permissions-group.component'
import { IfOwnerDirective } from './directives/if-owner.directive'
import { IfObjectPermissionsDirective } from './directives/if-object-permissions.directive'
import { PermissionsDialogComponent } from './components/common/permissions-dialog/permissions-dialog.component'
import { PermissionsFormComponent } from './components/common/input/permissions/permissions-form/permissions-form.component'
import { PermissionsFilterDropdownComponent } from './components/common/permissions-filter-dropdown/permissions-filter-dropdown.component'
import { UsernamePipe } from './pipes/username.pipe'
import { LogoComponent } from './components/common/logo/logo.component'
import { IsNumberPipe } from './pipes/is-number.pipe'
import { ShareLinksDropdownComponent } from './components/common/share-links-dropdown/share-links-dropdown.component'
import { WorkflowsComponent } from './components/manage/workflows/workflows.component'
import { WorkflowEditDialogComponent } from './components/common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { MailComponent } from './components/manage/mail/mail.component'
import { UsersAndGroupsComponent } from './components/admin/users-groups/users-groups.component'
import { DragDropModule } from '@angular/cdk/drag-drop'
import { FileDropComponent } from './components/file-drop/file-drop.component'
import { CustomFieldsComponent } from './components/manage/custom-fields/custom-fields.component'
import { CustomFieldEditDialogComponent } from './components/common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { CustomFieldsDropdownComponent } from './components/common/custom-fields-dropdown/custom-fields-dropdown.component'
import { ProfileEditDialogComponent } from './components/common/profile-edit-dialog/profile-edit-dialog.component'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import { DocumentLinkComponent } from './components/common/input/document-link/document-link.component'
import { PreviewPopupComponent } from './components/common/preview-popup/preview-popup.component'
import { SwitchComponent } from './components/common/input/switch/switch.component'
import { ConfigComponent } from './components/admin/config/config.component'
import { FileComponent } from './components/common/input/file/file.component'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from './components/common/confirm-button/confirm-button.component'
import { MonetaryComponent } from './components/common/input/monetary/monetary.component'
import { SystemStatusDialogComponent } from './components/common/system-status-dialog/system-status-dialog.component'
import { NgxFilesizeModule } from 'ngx-filesize'
import { RotateConfirmDialogComponent } from './components/common/confirm-dialog/rotate-confirm-dialog/rotate-confirm-dialog.component'
import { MergeConfirmDialogComponent } from './components/common/confirm-dialog/merge-confirm-dialog/merge-confirm-dialog.component'
import { SplitConfirmDialogComponent } from './components/common/confirm-dialog/split-confirm-dialog/split-confirm-dialog.component'
import { DocumentHistoryComponent } from './components/document-history/document-history.component'
import { DragDropSelectComponent } from './components/common/input/drag-drop-select/drag-drop-select.component'
import { CustomFieldDisplayComponent } from './components/common/custom-field-display/custom-field-display.component'
import { GlobalSearchComponent } from './components/app-frame/global-search/global-search.component'
import { HotkeyDialogComponent } from './components/common/hotkey-dialog/hotkey-dialog.component'
import { DeletePagesConfirmDialogComponent } from './components/common/confirm-dialog/delete-pages-confirm-dialog/delete-pages-confirm-dialog.component'
import { TrashComponent } from './components/admin/trash/trash.component'
import {
  airplane,
  archive,
  arrowClockwise,
  arrowCounterclockwise,
  arrowDown,
  arrowLeft,
  arrowRepeat,
  arrowRight,
  arrowRightShort,
  arrowUpRight,
  asterisk,
  bodyText,
  boxArrowUp,
  boxArrowUpRight,
  boxes,
  calendar,
  calendarEvent,
  calendarEventFill,
  cardChecklist,
  cardHeading,
  caretDown,
  caretUp,
  chatLeftText,
  check,
  check2All,
  checkAll,
  checkCircleFill,
  checkLg,
  chevronDoubleLeft,
  chevronDoubleRight,
  clipboard,
  clipboardCheck,
  clipboardCheckFill,
  clipboardFill,
  dash,
  dashCircle,
  diagram3,
  dice5,
  doorOpen,
  download,
  envelope,
  envelopeAt,
  exclamationCircleFill,
  exclamationTriangle,
  exclamationTriangleFill,
  eye,
  fileEarmark,
  fileEarmarkCheck,
  fileEarmarkFill,
  fileEarmarkLock,
  fileEarmarkMinus,
  files,
  fileText,
  filter,
  folder,
  folderFill,
  funnel,
  gear,
  grid,
  gripVertical,
  hash,
  hddStack,
  house,
  infoCircle,
  journals,
  link,
  listTask,
  listUl,
  pencil,
  people,
  peopleFill,
  person,
  personCircle,
  personFill,
  personFillLock,
  personLock,
  personSquare,
  plus,
  plusCircle,
  questionCircle,
  scissors,
  search,
  slashCircle,
  sliders2Vertical,
  sortAlphaDown,
  sortAlphaUpAlt,
  tagFill,
  tag,
  tags,
  textIndentLeft,
  textLeft,
  threeDots,
  threeDotsVertical,
  trash,
  uiRadios,
  upcScan,
  x,
  xLg,
} from 'ngx-bootstrap-icons'

const icons = {
  airplane,
  archive,
  arrowClockwise,
  arrowCounterclockwise,
  arrowDown,
  arrowLeft,
  arrowRepeat,
  arrowRight,
  arrowRightShort,
  arrowUpRight,
  asterisk,
  bodyText,
  boxArrowUp,
  boxArrowUpRight,
  boxes,
  calendar,
  calendarEvent,
  calendarEventFill,
  cardChecklist,
  cardHeading,
  caretDown,
  caretUp,
  chatLeftText,
  check,
  check2All,
  checkAll,
  checkCircleFill,
  checkLg,
  chevronDoubleLeft,
  chevronDoubleRight,
  clipboard,
  clipboardCheck,
  clipboardCheckFill,
  clipboardFill,
  dash,
  dashCircle,
  diagram3,
  dice5,
  doorOpen,
  download,
  envelope,
  envelopeAt,
  exclamationCircleFill,
  exclamationTriangle,
  exclamationTriangleFill,
  eye,
  fileEarmark,
  fileEarmarkCheck,
  fileEarmarkFill,
  fileEarmarkLock,
  fileEarmarkMinus,
  files,
  fileText,
  filter,
  folder,
  folderFill,
  funnel,
  gear,
  grid,
  gripVertical,
  hash,
  hddStack,
  house,
  infoCircle,
  journals,
  link,
  listTask,
  listUl,
  pencil,
  people,
  peopleFill,
  person,
  personCircle,
  personFill,
  personFillLock,
  personLock,
  personSquare,
  plus,
  plusCircle,
  questionCircle,
  scissors,
  search,
  slashCircle,
  sliders2Vertical,
  sortAlphaDown,
  sortAlphaUpAlt,
  tagFill,
  tag,
  tags,
  textIndentLeft,
  textLeft,
  threeDots,
  threeDotsVertical,
  trash,
  uiRadios,
  upcScan,
  x,
  xLg,
}

import localeAf from '@angular/common/locales/af'
import localeAr from '@angular/common/locales/ar'
import localeBe from '@angular/common/locales/be'
import localeBg from '@angular/common/locales/bg'
import localeCa from '@angular/common/locales/ca'
import localeCs from '@angular/common/locales/cs'
import localeDa from '@angular/common/locales/da'
import localeDe from '@angular/common/locales/de'
import localeEl from '@angular/common/locales/el'
import localeEnGb from '@angular/common/locales/en-GB'
import localeEs from '@angular/common/locales/es'
import localeFi from '@angular/common/locales/fi'
import localeFr from '@angular/common/locales/fr'
import localeHu from '@angular/common/locales/hu'
import localeIt from '@angular/common/locales/it'
import localeJa from '@angular/common/locales/ja'
import localeLb from '@angular/common/locales/lb'
import localeNl from '@angular/common/locales/nl'
import localeNo from '@angular/common/locales/no'
import localePl from '@angular/common/locales/pl'
import localePt from '@angular/common/locales/pt'
import localeRo from '@angular/common/locales/ro'
import localeRu from '@angular/common/locales/ru'
import localeSk from '@angular/common/locales/sk'
import localeSl from '@angular/common/locales/sl'
import localeSr from '@angular/common/locales/sr'
import localeSv from '@angular/common/locales/sv'
import localeTr from '@angular/common/locales/tr'
import localeUk from '@angular/common/locales/uk'
import localeZh from '@angular/common/locales/zh'

registerLocaleData(localeAf)
registerLocaleData(localeAr)
registerLocaleData(localeBe)
registerLocaleData(localeBg)
registerLocaleData(localeCa)
registerLocaleData(localeCs)
registerLocaleData(localeDa)
registerLocaleData(localeDe)
registerLocaleData(localeEl)
registerLocaleData(localeEnGb)
registerLocaleData(localeEs)
registerLocaleData(localeFi)
registerLocaleData(localeFr)
registerLocaleData(localeHu)
registerLocaleData(localeIt)
registerLocaleData(localeJa)
registerLocaleData(localeLb)
registerLocaleData(localeNl)
registerLocaleData(localeNo)
registerLocaleData(localePl)
registerLocaleData(localePt, 'pt-BR')
registerLocaleData(localePt, 'pt-PT')
registerLocaleData(localeRo)
registerLocaleData(localeRu)
registerLocaleData(localeSk)
registerLocaleData(localeSl)
registerLocaleData(localeSr)
registerLocaleData(localeSv)
registerLocaleData(localeTr)
registerLocaleData(localeUk)
registerLocaleData(localeZh)

function initializeApp(settings: SettingsService) {
  return () => {
    return settings.initializeSettings()
  }
}

@NgModule({
  declarations: [
    AppComponent,
    DocumentListComponent,
    DocumentDetailComponent,
    DashboardComponent,
    TagListComponent,
    DocumentTypeListComponent,
    CorrespondentListComponent,
    StoragePathListComponent,
    LogsComponent,
    SettingsComponent,
    NotFoundComponent,
    CorrespondentEditDialogComponent,
    ConfirmDialogComponent,
    TagEditDialogComponent,
    DocumentTypeEditDialogComponent,
    StoragePathEditDialogComponent,
    TagComponent,
    ClearableBadgeComponent,
    PageHeaderComponent,
    AppFrameComponent,
    ToastsComponent,
    FilterEditorComponent,
    FilterableDropdownComponent,
    ToggleableDropdownButtonComponent,
    DatesDropdownComponent,
    DocumentCardLargeComponent,
    DocumentCardSmallComponent,
    BulkEditorComponent,
    TextComponent,
    SelectComponent,
    CheckComponent,
    UrlComponent,
    PasswordComponent,
    SaveViewConfigDialogComponent,
    TagsComponent,
    IfPermissionsDirective,
    SortableDirective,
    SavedViewWidgetComponent,
    StatisticsWidgetComponent,
    UploadFileWidgetComponent,
    WidgetFrameComponent,
    WelcomeWidgetComponent,
    YesNoPipe,
    FileSizePipe,
    FilterPipe,
    DocumentTitlePipe,
    MetadataCollapseComponent,
    SelectDialogComponent,
    NumberComponent,
    SafeUrlPipe,
    SafeHtmlPipe,
    CustomDatePipe,
    DateComponent,
    ColorComponent,
    DocumentAsnComponent,
    DocumentNotesComponent,
    TasksComponent,
    UserEditDialogComponent,
    GroupEditDialogComponent,
    PermissionsSelectComponent,
    MailAccountEditDialogComponent,
    MailRuleEditDialogComponent,
    PermissionsUserComponent,
    PermissionsGroupComponent,
    IfOwnerDirective,
    IfObjectPermissionsDirective,
    PermissionsDialogComponent,
    PermissionsFormComponent,
    PermissionsFilterDropdownComponent,
    UsernamePipe,
    LogoComponent,
    IsNumberPipe,
    ShareLinksDropdownComponent,
    WorkflowsComponent,
    WorkflowEditDialogComponent,
    MailComponent,
    UsersAndGroupsComponent,
    FileDropComponent,
    CustomFieldsComponent,
    CustomFieldEditDialogComponent,
    CustomFieldsDropdownComponent,
    ProfileEditDialogComponent,
    DocumentLinkComponent,
    PreviewPopupComponent,
    SwitchComponent,
    ConfigComponent,
    FileComponent,
    ConfirmButtonComponent,
    MonetaryComponent,
    SystemStatusDialogComponent,
    RotateConfirmDialogComponent,
    MergeConfirmDialogComponent,
    SplitConfirmDialogComponent,
    DocumentHistoryComponent,
    DragDropSelectComponent,
    CustomFieldDisplayComponent,
    GlobalSearchComponent,
    HotkeyDialogComponent,
    DeletePagesConfirmDialogComponent,
    TrashComponent,
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    NgbModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    PdfViewerModule,
    NgxFileDropModule,
    NgSelectModule,
    ColorSliderModule,
    TourNgBootstrapModule,
    DragDropModule,
    NgxBootstrapIconsModule.pick(icons),
    NgxFilesizeModule,
  ],
  providers: [
    {
      provide: APP_INITIALIZER,
      useFactory: initializeApp,
      deps: [SettingsService],
      multi: true,
    },
    DatePipe,
    CookieService,
    {
      provide: HTTP_INTERCEPTORS,
      useClass: CsrfInterceptor,
      multi: true,
    },
    {
      provide: HTTP_INTERCEPTORS,
      useClass: ApiVersionInterceptor,
      multi: true,
    },
    FilterPipe,
    DocumentTitlePipe,
    { provide: NgbDateAdapter, useClass: ISODateAdapter },
    { provide: NgbDateParserFormatter, useClass: LocalizedDateParserFormatter },
    PermissionsGuard,
    DirtyDocGuard,
    DirtySavedViewGuard,
    UsernamePipe,
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
