import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { AppFrameComponent } from './components/app-frame/app-frame.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { DocumentDetailComponent } from './components/document-detail/document-detail.component';
import { DocumentListComponent } from './components/document-list/document-list.component';
import { LoginComponent } from './components/login/login.component';
import { CorrespondentListComponent } from './components/manage/correspondent-list/correspondent-list.component';
import { DocumentTypeListComponent } from './components/manage/document-type-list/document-type-list.component';
import { LogsComponent } from './components/manage/logs/logs.component';
import { SettingsComponent } from './components/manage/settings/settings.component';
import { TagListComponent } from './components/manage/tag-list/tag-list.component';
import { NotFoundComponent } from './components/not-found/not-found.component';
import { SearchComponent } from './components/search/search.component';
import { AuthGuardService } from './services/auth-guard.service';

const routes: Routes = [
  {path: '', redirectTo: 'dashboard', pathMatch: 'full'},
  {path: '', component: AppFrameComponent, children: [
    {path: 'dashboard', component: DashboardComponent, canActivate: [AuthGuardService] },
    {path: 'documents', component: DocumentListComponent, canActivate: [AuthGuardService] },
    {path: 'view/:name', component: DocumentListComponent, canActivate: [AuthGuardService] },
    {path: 'search', component: SearchComponent, canActivate: [AuthGuardService] },
    {path: 'documents/:id', component: DocumentDetailComponent, canActivate: [AuthGuardService] },
  
    {path: 'tags', component: TagListComponent, canActivate: [AuthGuardService] },
    {path: 'documenttypes', component: DocumentTypeListComponent, canActivate: [AuthGuardService] },
    {path: 'correspondents', component: CorrespondentListComponent, canActivate: [AuthGuardService] },
    {path: 'logs', component: LogsComponent, canActivate: [AuthGuardService] },
    {path: 'settings', component: SettingsComponent, canActivate: [AuthGuardService] },
  ]}, 

  {path: 'login', component: LoginComponent },
  {path: '404', component: NotFoundComponent},
  {path: '**', redirectTo: '/404', pathMatch: 'full'}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
