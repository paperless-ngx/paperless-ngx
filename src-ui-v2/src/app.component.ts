import { Component } from '@angular/core'
import { RouterModule } from '@angular/router'

@Component({
    selector: 'app-root',
    standalone: true,
    imports: [RouterModule],
    template: `<router-outlet></router-outlet>`,
})
export class AppComponent {
}
