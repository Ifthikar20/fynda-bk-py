"""
Management command to create editorial-quality sample blog posts
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from blog.models import Post, Category, Tag


class Command(BaseCommand):
    help = 'Create editorial-quality sample blog posts'

    def handle(self, *args, **options):
        # Create editorial categories
        editorial_cat, _ = Category.objects.get_or_create(
            name='Editorial',
            slug='editorial',
            defaults={'description': 'In-depth fashion stories and cultural commentary'}
        )
        trends_cat, _ = Category.objects.get_or_create(
            name='Trends',
            slug='trends',
            defaults={'description': 'What\'s defining fashion right now'}
        )
        style_cat, _ = Category.objects.get_or_create(
            name='Style',
            slug='style',
            defaults={'description': 'Timeless advice for the modern wardrobe'}
        )
        designers_cat, _ = Category.objects.get_or_create(
            name='Designers',
            slug='designers',
            defaults={'description': 'Profiles and insights from fashion\'s most influential voices'}
        )

        # Create tags
        luxury_tag, _ = Tag.objects.get_or_create(name='luxury', slug='luxury')
        reissue_tag, _ = Tag.objects.get_or_create(name='reissues', slug='reissues')
        bags_tag, _ = Tag.objects.get_or_create(name='bags', slug='bags')
        minimalism_tag, _ = Tag.objects.get_or_create(name='minimalism', slug='minimalism')
        runway_tag, _ = Tag.objects.get_or_create(name='runway', slug='runway')
        culture_tag, _ = Tag.objects.get_or_create(name='culture', slug='culture')

        # Post 1: Featured Editorial (like the Lyst example)
        post1, created = Post.objects.update_or_create(
            slug='why-this-seasons-hottest-bags-are-reissues',
            defaults={
                'title': "Why This Season's Hottest Bags Are Reissues",
                'meta_description': 'Fashion is in its memory phase. When a house brings back a bag, it\'s reactivating cultural capital: recognition, nostalgia, and authority.',
                'content': '''<p>Fashion is in its memory phase. In an era defined by micro-trends, algorithmic taste and constant newness, luxury is slowing down and looking backward. When a house brings back a bag, it's not just reviving a silhouette, it's reactivating cultural capital: recognition, nostalgia, and the authority that comes from having endured.</p>

<p>For a generation fluent in archives, resale platforms, and fashion history, familiarity isn't boring, it's referential. Younger consumers are as obsessed with fashion history as they are with fashion future. Reissues anchor trendy cycles in a deeper narrative. They offer the thrill of discovery, the reassurance of legacy, and a tangible link to the stylistic stories that shape how we express ourselves. Rediscovery has become a design strategy: it's less about inventing shapes from scratch and more about surfacing identities that already exist and matter.</p>

<h2>The Return of Icons</h2>

<p>This season's most desirable bags reflect that shift. The return of the Chloé Paddington taps directly into early-2000s mythology, bringing back its slouchy confidence and signature padlock. Saint Laurent's Mombasa channels Tom Ford-era sensuality, proving relaxed, sculptural shapes still resonate. Meanwhile, the quiet revival of Celine's Phantom signals a renewed appetite for soft minimalism and understated authority, while Balenciaga's City reasserts its place as the original off-duty cool-girl bag, worn-in and unapologetically real.</p>

<blockquote>Reissues aren't about recycling ideas; they're about reasserting lineage. This season, the most coveted bags are a proof that luxury houses aren't just selling accessories, they're selling narratives.</blockquote>

<h2>What This Means for You</h2>

<p>The takeaway for shoppers is clear: invest in pieces with staying power. These aren't fleeting trends but rather proven designs that have already weathered the cycles of fashion. When you carry a Paddington or a City bag, you're not just following a trend—you're participating in fashion history.</p>

<p>At Fynda, we track deals on these iconic pieces across hundreds of retailers. When a classic bag goes on sale, we'll make sure you know about it.</p>''',
                'category': editorial_cat,
                'status': 'published',
                'published_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {post1.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated: {post1.title}'))
        post1.tags.set([luxury_tag, reissue_tag, bags_tag])

        # Post 2: Trend Analysis
        post2, created = Post.objects.update_or_create(
            slug='the-quiet-luxury-paradox',
            defaults={
                'title': "The Quiet Luxury Paradox: Why Less Is More Expensive",
                'meta_description': 'Stealth wealth dressing has redefined what it means to look expensive. But the irony runs deeper than you think.',
                'content': '''<p>The fashion industry has a new north star: nothing. Not nothing literally, but the studied absence of logos, the deliberate invisibility of brand signifiers, and the elevation of materials so exquisite they need no introduction. Welcome to the age of quiet luxury.</p>

<p>The paradox, of course, is that this particular version of nothing costs more than everything. A cashmere coat without a label can run four figures. Unbranded leather goods from The Row or Loro Piana command prices that would make a logo-emblazoned competitor blush. The message is clear: if you know, you know. And if you don't? You're not the customer.</p>

<h2>The Rise of Stealth Wealth</h2>

<p>This shift didn't happen overnight. It's the natural counter-movement to a decade of maximalism, logomania, and Instagram-ready fashion. As algorithms served us increasingly similar content, the desire to opt out—to communicate status through subtraction—became its own form of expression.</p>

<figure class="image-left">
<img src="https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=600&h=800&fit=crop" alt="Minimalist fashion">
<figcaption>Quiet luxury prioritizes silhouette over signage</figcaption>
</figure>

<p>Brands like Bottega Veneta led the charge under Daniel Lee, proving that recognition could come from signature weaves rather than printed initials. The Row built an empire on the premise that the richest-looking clothes needed no explanation. Brunello Cucinelli made his fortune selling cashmere to people who could afford to not talk about it.</p>

<h2>What It Means for the Market</h2>

<p>For deal-seekers, this creates an interesting opportunity. As trend cycles accelerate, last season's logo-heavy pieces hit the sale racks faster. Meanwhile, quiet luxury pieces—designed to transcend seasons—hold their value. The economics shift in favor of investment dressing.</p>

<p>At Fynda, we're seeing this play out in real time. Our users increasingly search for "quality basics," "cashmere," and "minimal design"—terms that would have felt generic a decade ago but now signal a specific aesthetic aspiration.</p>''',
                'category': trends_cat,
                'status': 'published',
                'published_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {post2.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated: {post2.title}'))
        post2.tags.set([minimalism_tag, luxury_tag, culture_tag])

        # Post 3: Designer Profile
        post3, created = Post.objects.update_or_create(
            slug='phoebe-philos-return-what-we-learned',
            defaults={
                'title': "Phoebe Philo's Return: What We Learned From the Sellout",
                'meta_description': 'When Phoebe Philo launched her eponymous brand, everything sold out in hours. What does that tell us about fashion today?',
                'content': '''<p>When Phoebe Philo's eponymous brand quietly launched its debut collection last year, the fashion world held its collective breath. Within hours, virtually everything was gone. No aggressive marketing, no celebrity partnerships, no influencer seedings. Just design—and a customer base that had been waiting a very long time.</p>

<p>The sellout wasn't just a commercial success; it was a referendum on what fashion audiences actually want. After years of being told they needed viral moments and algorithmic approval, here was proof that some customers just want beautiful clothes from a designer they trust.</p>

<h2>The Philo Effect</h2>

<p>Philo's tenure at Celine (before the accent) defined a decade of fashion. Her influence extended beyond the clothes themselves—she shaped an entire approach to modern femininity: intelligent, controlled, unapologetic. When she stepped away in 2017, she left a vacuum that no designer has quite filled.</p>

<blockquote>Her return reminds us that fashion still has room for auteurs—designers whose vision is so coherent that it creates its own market.</blockquote>

<p>The new collection picks up where she left off while acknowledging time has passed. The silhouettes are familiar yet evolved. The materials speak for themselves. And the prices—undeniably steep—haven't deterred the faithful.</p>

<h2>Lessons for the Industry</h2>

<p>What Philo's success suggests is that there's a significant audience underserved by contemporary fashion. Not everyone wants drops and collaborations. Some customers prefer to wait for something worth waiting for.</p>

<p>For our users at Fynda, the lesson is this: great design holds its value. Whether you're shopping new or secondhand, prioritize pieces with real point of view over trend-chasing ephemera. Your wardrobe—and wallet—will thank you.</p>''',
                'category': designers_cat,
                'status': 'published',
                'published_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {post3.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated: {post3.title}'))
        post3.tags.set([luxury_tag, culture_tag])

        # Post 4: Style Guide
        post4, created = Post.objects.update_or_create(
            slug='the-art-of-the-capsule-wardrobe',
            defaults={
                'title': "The Art of the Capsule Wardrobe: A Modern Guide",
                'meta_description': 'Forget the 33-item rule. A truly effective capsule wardrobe is about intention, not arithmetic.',
                'content': '''<p>The capsule wardrobe has become something of a meme—a Pinterest fantasy of perfectly folded neutrals and the promise of never having to think about clothes again. But the concept, stripped of its viral packaging, contains genuine wisdom worth revisiting.</p>

<p>At its core, a capsule wardrobe is simply a curated collection of clothes that work together. The magic number varies depending on who you ask—33 items, 37 items, 40 items—but the specific count matters less than the underlying principle: buy less, choose better.</p>

<h2>The Framework</h2>

<p>Rather than prescribing exact numbers, consider these categories as starting points:</p>

<p><strong>The Foundation</strong>—pieces you reach for without thinking. A white shirt that fits perfectly. Dark trousers that work for everything. A coat that handles most weather conditions.</p>

<p><strong>The Workhorses</strong>—items that bridge casual and dressed-up. A blazer in a versatile color. Well-made denim. Shoes that can walk miles without looking like they're trying to.</p>

<p><strong>The Punctuation</strong>—pieces that add character. A vintage find. Something in an unexpected color. The item that makes the outfit yours.</p>

<h2>Quality Over Quantity</h2>

<p>The economic logic of capsule dressing is counterintuitive: spend more per piece to spend less overall. A $300 coat worn 200 times costs $1.50 per wear. A $60 coat worn 20 times before falling apart costs $3 per wear. The math consistently favors quality.</p>

<p>This is where Fynda comes in. We help you find those quality pieces at the best possible prices, so investing in your wardrobe doesn't mean breaking the bank.</p>''',
                'category': style_cat,
                'status': 'published',
                'published_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {post4.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated: {post4.title}'))
        post4.tags.set([minimalism_tag])

        # Post 5: Trend Report
        post5, created = Post.objects.update_or_create(
            slug='spring-2026-runway-decoded',
            defaults={
                'title': "Spring 2026 Runway Decoded: What Actually Matters",
                'meta_description': 'Beyond the spectacle, here\'s what the spring shows are really telling us about where fashion is headed.',
                'content': '''<p>Fashion weeks generate noise. Dozens of shows, hundreds of looks, thousands of social media posts—the volume can obscure the signal. But if you step back from the chaos, clear patterns emerge. Here's what spring 2026 is really about.</p>

<h2>The Return of Softness</h2>

<p>After seasons of sharp tailoring and rigid structures, designers are embracing fluidity. Draped dresses, relaxed suiting, and fabrics that move with the body dominated the runways. This isn't about formlessness—it's about ease without sloppiness.</p>

<p>At Bottega Veneta, Matthieu Blazy continued his exploration of leather as a supple, almost textile material. At The Row, the Olsen twins showed layers of sand-colored silks that seemed to float rather than hang. Even at traditionally structured houses like Dior, there was a noticeable softening of edges.</p>

<h2>Color Confidence</h2>

<p>The quiet luxury color palette—all those greiges and caramels and off-whites—isn't going anywhere. But it's being punctuated by moments of bold color. Chartreuse at Valentino. Electric blue at Ferragamo. Saturated red everywhere.</p>

<figure class="image-right">
<img src="https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&h=800&fit=crop" alt="Runway fashion">
<figcaption>Spring 2026 embraces bold color accents</figcaption>
</figure>

<p>The message: if you're going to add color, commit to it. No pastels, no half-measures.</p>

<h2>Practical Application</h2>

<p>For the average shopper (which is to say, someone not buying runway), here's the translation:</p>

<p>Invest in pieces that drape well and feel good to wear. The structured blazer isn't dead, but it should probably live alongside something softer now. And consider adding one bold color piece to your rotation—not as a statement, but as punctuation.</p>

<p>At Fynda, we're already tracking deals on pieces that reflect these directions. Good design doesn't have to cost a fortune.</p>''',
                'category': trends_cat,
                'status': 'published',
                'published_at': timezone.now(),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {post5.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated: {post5.title}'))
        post5.tags.set([runway_tag, culture_tag])

        self.stdout.write(self.style.SUCCESS('\n✅ Editorial blog posts created successfully!'))
