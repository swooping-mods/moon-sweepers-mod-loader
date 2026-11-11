namespace Fixture;

#if CONSUMER
public sealed class Consumer : IContract
{
    public void Method() { }
    public static bool Use(RemovedType value) { Api.Removed(1); return Api.Flag; }
}
#else
public interface IContract
{
    void Method();
#if MODERN
    int Config { get; }
#endif
}

public static class Api
{
#if LEGACY
    public static bool Flag;
    public static void Removed(int value) { }
#else
    public static void Removed(string value) { }
#endif
}

#if LEGACY
public class RemovedType { }
#endif
#endif
