import { NgModule } from '@angular/core'
import { MarkdownModule } from 'ngx-markdown'
import { AppComponent } from './app.component'

@NgModule({
  declarations: [AppComponent],
  imports: [MarkdownModule.forRoot()],
  providers: [],
  bootstrap: [AppComponent],
})
export class AppModule {}
