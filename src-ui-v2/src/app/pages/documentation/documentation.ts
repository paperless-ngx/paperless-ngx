import { CommonModule } from '@angular/common'
import { Component } from '@angular/core'

@Component({
    selector: 'app-documentation',
    standalone: true,
    imports: [CommonModule],
    template: `
        <div class="card">
            <div class="font-semibold text-2xl mb-4">Documentation</div>
            <div class="font-semibold text-xl mb-4">Get Started</div>
            <p class="text-lg mb-4">Sakai is an application template for Angular and is distributed as a CLI project. Current versions is Angular v19 with PrimeNG v19. In case CLI is not installed already, use the command below to set it up.</p>
            <pre class="app-code">
<code>npm install -g &#64;angular/cli</code></pre>
            <p class="text-lg mb-4">
                Once CLI is ready in your system, extract the contents of the zip file distribution, cd to the directory, install the libraries from npm and then execute "ng serve" to run the application in your local environment.
            </p>
            <pre class="app-code">
<code>git clone https://github.com/primefaces/sakai-ng
npm install
ng serve</code></pre>

            <p class="text-lg mb-4">The application should run at <i class="bg-highlight px-2 py-1 rounded-border not-italic text-base">http://localhost:4200/</i> to view the application in your local environment.</p>

            <div class="font-semibold text-xl mb-4">Structure</div>
            <p class="text-lg mb-4">Templates consists of a couple folders, demos and layout have been separated so that you can easily identify what is necessary for your application.</p>
            <ul class="leading-normal list-disc pl-8 text-lg mb-4">
                <li><span class="text-primary font-medium">src/app/layout</span>: Main layout files, needs to be present.</li>
                <li><span class="text-primary font-medium">src/app/pages</span>: Demo content like Dashboard.</li>
                <li><span class="text-primary font-medium">src/assets/demo</span>: Assets used in demos</li>
                <li><span class="text-primary font-medium">src/assets/layout</span>: SCSS files of the main layout</li>
            </ul>

            <div class="font-semibold text-xl mb-4">Menu</div>
            <p class="text-lg mb-4">
                Main menu is defined at <span class="bg-highlight px-2 py-1 rounded-border not-italic text-base">src/app/layout/component/app.menu.ts</span> file. Update the
                <i class="bg-highlight px-2 py-1 rounded-border not-italic text-base">model</i> property to define your own menu items.
            </p>

            <div class="font-semibold text-xl mb-4">Layout Service</div>
            <p class="text-lg mb-4">
                <span class="bg-highlight px-2 py-1 rounded-border not-italic text-base">src/app/layout/service/layout.service.ts</span> is a service that manages layout state changes, including dark mode, PrimeNG theme, menu modes, and states.
            </p>

            <div class="font-semibold text-xl mb-4">Tailwind CSS</div>
            <p class="text-lg mb-4">The demo pages are developed with Tailwind CSS however the core application shell uses custom CSS.</p>

            <div class="font-semibold text-xl mb-4">Variables</div>
            <p class="text-lg mb-4">
                CSS variables used in the template are derived from the applied PrimeNG theme. Customize them through the CSS variables in <span class="bg-highlight px-2 py-1 rounded-border not-italic text-base">src/assets/layout/variables</span>.
            </p>
        </div>
    `,
    styles: `
        @media screen and (max-width: 991px) {
            .video-container {
                position: relative;
                width: 100%;
                height: 0;
                padding-bottom: 56.25%;

                iframe {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                }
            }
        }
    `,
})
export class Documentation {
}
