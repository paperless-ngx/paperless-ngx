import { NgModule } from '@angular/core';
import { AppComponent } from './app.component';
import { MarkdownModule } from 'ngx-markdown';

@NgModule({
    declarations: [
        AppComponent
    ],
    imports: [
        MarkdownModule.forRoot()
    ],
    providers: [],
    bootstrap: [AppComponent]
})
export class AppModule { } 