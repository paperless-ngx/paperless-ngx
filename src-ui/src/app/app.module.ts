import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { DocumentListComponent } from './components/document-list/document-list.component';
import { DocumentDetailComponent } from './components/document-detail/document-detail.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { TagListComponent } from './components/manage/tag-list/tag-list.component';
import { DocumentTypeListComponent } from './components/manage/document-type-list/document-type-list.component';
import { LogsComponent } from './components/manage/logs/logs.component';
import { SettingsComponent } from './components/manage/settings/settings.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { NotFoundComponent } from './components/not-found/not-found.component';
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component';
import { ConfirmDialogComponent } from './components/common/confirm-dialog/confirm-dialog.component';
import { CorrespondentEditDialogComponent } from './components/manage/correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { TagEditDialogComponent } from './components/manage/tag-list/tag-edit-dialog/tag-edit-dialog.component';
import { DocumentTypeEditDialogComponent } from './components/manage/document-type-list/document-type-edit-dialog/document-type-edit-dialog.component';
import { TagComponent } from './components/common/tag/tag.component';
import { SearchComponent } from './components/search/search.component';
import { ResultHighlightComponent } from './components/search/result-highlight/result-highlight.component';
import { PageHeaderComponent } from './components/common/page-header/page-header.component';
import { AppFrameComponent } from './components/app-frame/app-frame.component';
import { ToastsComponent } from './components/common/toasts/toasts.component';
import { FilterEditorComponent } from './components/filter-editor/filter-editor.component';
import { DocumentCardLargeComponent } from './components/document-list/document-card-large/document-card-large.component';
import { DocumentCardSmallComponent } from './components/document-list/document-card-small/document-card-small.component';
import { NgxFileDropModule } from 'ngx-file-drop';
import { TextComponent } from './components/common/input/text/text.component';
import { SelectComponent } from './components/common/input/select/select.component';
import { CheckComponent } from './components/common/input/check/check.component';
import { SaveViewConfigDialogComponent } from './components/document-list/save-view-config-dialog/save-view-config-dialog.component';
import { InfiniteScrollModule } from 'ngx-infinite-scroll';
import { DateTimeComponent } from './components/common/input/date-time/date-time.component';
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
import { DocumentTitlePipe } from './pipes/document-title.pipe';

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
    SearchComponent,
    ResultHighlightComponent,
    PageHeaderComponent,
    AppFrameComponent,
    ToastsComponent,
    FilterEditorComponent,
    DocumentCardLargeComponent,
    DocumentCardSmallComponent,
    TextComponent,
    SelectComponent,
    CheckComponent,
    SaveViewConfigDialogComponent,
    DateTimeComponent,
    TagsComponent,
    SortableDirective,
    SavedViewWidgetComponent,
    StatisticsWidgetComponent,
    UploadFileWidgetComponent,
    WidgetFrameComponent,
    WelcomeWidgetComponent,
    YesNoPipe,
    FileSizePipe,
    DocumentTitlePipe
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
    PdfViewerModule
  ],
  providers: [
    DatePipe,
    CookieService, {
      provide: HTTP_INTERCEPTORS,
      useClass: CsrfInterceptor,
      multi: true
    }
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
