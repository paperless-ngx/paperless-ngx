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
import { LoginComponent } from './components/login/login.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { SafePipe } from './pipes/safe.pipe';
import { NotFoundComponent } from './components/not-found/not-found.component';
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component';
import { DeleteDialogComponent } from './components/common/delete-dialog/delete-dialog.component';
import { CorrespondentEditDialogComponent } from './components/manage/correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { TagEditDialogComponent } from './components/manage/tag-list/tag-edit-dialog/tag-edit-dialog.component';
import { DocumentTypeEditDialogComponent } from './components/manage/document-type-list/document-type-edit-dialog/document-type-edit-dialog.component';
import { TagComponent } from './components/common/tag/tag.component';
import { SearchComponent } from './components/search/search.component';
import { ResultHightlightComponent } from './components/search/result-hightlight/result-hightlight.component';
import { PageHeaderComponent } from './components/common/page-header/page-header.component';
import { AppFrameComponent } from './components/app-frame/app-frame.component';
import { ToastsComponent } from './components/common/toasts/toasts.component';
import { FilterEditorComponent } from './components/filter-editor/filter-editor.component';
import { AuthInterceptor } from './services/auth.interceptor';
import { DocumentCardLargeComponent } from './components/document-list/document-card-large/document-card-large.component';
import { DocumentCardSmallComponent } from './components/document-list/document-card-small/document-card-small.component';
import { NgxFileDropModule } from 'ngx-file-drop';
import { TextComponent } from './components/common/input/text/text.component';
import { SelectComponent } from './components/common/input/select/select.component';
import { CheckComponent } from './components/common/input/check/check.component';
import { SaveViewConfigDialogComponent } from './components/document-list/save-view-config-dialog/save-view-config-dialog.component';
import { InfiniteScrollModule } from 'ngx-infinite-scroll';
import { DateTimeComponent } from './components/common/input/date-time/date-time.component';

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
    LoginComponent,
    SafePipe,
    NotFoundComponent,
    CorrespondentEditDialogComponent,
    DeleteDialogComponent,
    TagEditDialogComponent,
    DocumentTypeEditDialogComponent,
    TagComponent,
    SearchComponent,
    ResultHightlightComponent,
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
    DateTimeComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    NgbModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    NgxFileDropModule,
    InfiniteScrollModule
  ],
  providers: [
    DatePipe,
    {
      provide: HTTP_INTERCEPTORS,
      useClass: AuthInterceptor,
      multi: true
    }
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
