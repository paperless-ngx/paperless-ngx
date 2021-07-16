import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { NgbDateAdapter, NgbDateParserFormatter, NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { DocumentListComponent } from './components/document-list/document-list.component';
import { DocumentDetailComponent } from './components/document-detail/document-detail.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { TagListComponent } from './components/manage/tag-list/tag-list.component';
import { DocumentTypeListComponent } from './components/manage/document-type-list/document-type-list.component';
import { LogsComponent } from './components/manage/logs/logs.component';
import { SettingsComponent } from './components/manage/settings/settings.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { DatePipe, registerLocaleData } from '@angular/common';
import { NotFoundComponent } from './components/not-found/not-found.component';
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component';
import { ConfirmDialogComponent } from './components/common/confirm-dialog/confirm-dialog.component';
import { CorrespondentEditDialogComponent } from './components/manage/correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { TagEditDialogComponent } from './components/manage/tag-list/tag-edit-dialog/tag-edit-dialog.component';
import { DocumentTypeEditDialogComponent } from './components/manage/document-type-list/document-type-edit-dialog/document-type-edit-dialog.component';
import { TagComponent } from './components/common/tag/tag.component';
import { PageHeaderComponent } from './components/common/page-header/page-header.component';
import { AppFrameComponent } from './components/app-frame/app-frame.component';
import { ToastsComponent } from './components/common/toasts/toasts.component';
import { FilterEditorComponent } from './components/document-list/filter-editor/filter-editor.component';
import { FilterableDropdownComponent } from './components/common/filterable-dropdown/filterable-dropdown.component';
import { ToggleableDropdownButtonComponent } from './components/common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';
import { DateDropdownComponent } from './components/common/date-dropdown/date-dropdown.component';
import { DocumentCardLargeComponent } from './components/document-list/document-card-large/document-card-large.component';
import { DocumentCardSmallComponent } from './components/document-list/document-card-small/document-card-small.component';
import { BulkEditorComponent } from './components/document-list/bulk-editor/bulk-editor.component';
import { NgxFileDropModule } from 'ngx-file-drop';
import { TextComponent } from './components/common/input/text/text.component';
import { SelectComponent } from './components/common/input/select/select.component';
import { CheckComponent } from './components/common/input/check/check.component';
import { SaveViewConfigDialogComponent } from './components/document-list/save-view-config-dialog/save-view-config-dialog.component';
import { InfiniteScrollModule } from 'ngx-infinite-scroll';
import { TagsComponent } from './components/common/input/tags/tags.component';
import { SortableDirective } from './directives/sortable.directive';
import { CookieService } from 'ngx-cookie-service';
import { CsrfInterceptor } from './interceptors/csrf.interceptor';
import { SavedViewWidgetComponent } from './components/dashboard/widgets/saved-view-widget/saved-view-widget.component';
import { StatisticsWidgetComponent } from './components/dashboard/widgets/statistics-widget/statistics-widget.component';
import { UploadFileWidgetComponent } from './components/dashboard/widgets/upload-file-widget/upload-file-widget.component';
import { WidgetFrameComponent } from './components/dashboard/widgets/widget-frame/widget-frame.component';
import { PdfViewerModule } from 'ng2-pdf-viewer';
import { WelcomeWidgetComponent } from './components/dashboard/widgets/welcome-widget/welcome-widget.component';
import { YesNoPipe } from './pipes/yes-no.pipe';
import { FileSizePipe } from './pipes/file-size.pipe';
import { FilterPipe } from './pipes/filter.pipe';
import { DocumentTitlePipe } from './pipes/document-title.pipe';
import { MetadataCollapseComponent } from './components/document-detail/metadata-collapse/metadata-collapse.component';
import { SelectDialogComponent } from './components/common/select-dialog/select-dialog.component';
import { NgSelectModule } from '@ng-select/ng-select';
import { NumberComponent } from './components/common/input/number/number.component';
import { SafePipe } from './pipes/safe.pipe';
import { CustomDatePipe } from './pipes/custom-date.pipe';
import { DateComponent } from './components/common/input/date/date.component';
import { ISODateTimeAdapter } from './utils/ngb-iso-date-time-adapter';
import { LocalizedDateParserFormatter } from './utils/ngb-date-parser-formatter';
import { ApiVersionInterceptor } from './interceptors/api-version.interceptor';
import { ColorSliderModule } from 'ngx-color/slider';
import { ColorComponent } from './components/common/input/color/color.component';
import { DocumentAsnComponent } from './components/document-asn/document-asn.component';

import localeFr from '@angular/common/locales/fr';
import localeNl from '@angular/common/locales/nl';
import localeDe from '@angular/common/locales/de';
import localePt from '@angular/common/locales/pt';
import localeIt from '@angular/common/locales/it';
import localeEnGb from '@angular/common/locales/en-GB';
import localeRo from '@angular/common/locales/ro';
import localeRu from '@angular/common/locales/ru';
import localeEs from '@angular/common/locales/es';
import localePl from '@angular/common/locales/pl';
import localeSv from '@angular/common/locales/sv';
import localeLb from '@angular/common/locales/lb';


registerLocaleData(localeFr)
registerLocaleData(localeNl)
registerLocaleData(localeDe)
registerLocaleData(localePt, "pt-BR")
registerLocaleData(localePt, "pt-PT")
registerLocaleData(localeIt)
registerLocaleData(localeEnGb)
registerLocaleData(localeRo)
registerLocaleData(localeRu)
registerLocaleData(localeEs)
registerLocaleData(localePl)
registerLocaleData(localeSv)
registerLocaleData(localeLb)

@NgModule({
  declarations: [
    AppComponent,
    DocumentListComponent,
    DocumentDetailComponent,
    DashboardComponent,
    TagListComponent,
    CorrespondentListComponent,
    DocumentTypeListComponent,
    LogsComponent,
    SettingsComponent,
    NotFoundComponent,
    CorrespondentEditDialogComponent,
    ConfirmDialogComponent,
    TagEditDialogComponent,
    DocumentTypeEditDialogComponent,
    TagComponent,
    PageHeaderComponent,
    AppFrameComponent,
    ToastsComponent,
    FilterEditorComponent,
    FilterableDropdownComponent,
    ToggleableDropdownButtonComponent,
    DateDropdownComponent,
    DocumentCardLargeComponent,
    DocumentCardSmallComponent,
    BulkEditorComponent,
    TextComponent,
    SelectComponent,
    CheckComponent,
    SaveViewConfigDialogComponent,
    TagsComponent,
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
    SafePipe,
    CustomDatePipe,
    DateComponent,
    ColorComponent,
    DocumentAsnComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    NgbModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    NgxFileDropModule,
    InfiniteScrollModule,
    PdfViewerModule,
    NgSelectModule,
    ColorSliderModule
  ],
  providers: [
    DatePipe,
    CookieService, {
      provide: HTTP_INTERCEPTORS,
      useClass: CsrfInterceptor,
      multi: true
    },{
      provide: HTTP_INTERCEPTORS,
      useClass: ApiVersionInterceptor,
      multi: true
    },
    FilterPipe,
    DocumentTitlePipe,
    {provide: NgbDateAdapter, useClass: ISODateTimeAdapter},
    {provide: NgbDateParserFormatter, useClass: LocalizedDateParserFormatter}
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
